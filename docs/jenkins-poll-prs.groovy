// ============================================================
// jenkins-poll-prs.groovy
// 轮询 GitHub，发现变化时自动触发 pipeline-build
//
// 两种模式：
//   pr     — 监控所有 open PR，新 PR 或 PR 有新 commit 时触发
//   branch — 监控指定分支，分支有新 commit 时触发
//
// 用法：
//   1. Jenkins 新建 Freestyle Job「pr-poll」
//   2. 勾选 "This project is parameterized"，添加以下参数：
//        MONITOR_TYPE    String  默认 pr
//        MONITOR_BRANCH  String  默认 main
//        REPO_URL        String  默认 https://github.com/HuangPuStar/FenixAgent
//        TARGET_JOB      String  默认 PR-Pipeline-build
//        GITHUB_TOKEN    String  默认空（可选，提高 rate limit）
//        FORCE_RESET     String  默认 false（设为 true 清除状态，以全新首次运行状态触发所有 PR）
//   3. Build Triggers: H/2 * * * *  （每 2 分钟）
//   4. Build Steps → Execute system Groovy script → 粘贴本脚本
// ============================================================

import groovy.json.JsonSlurper
import groovy.json.JsonOutput

// ===================== 参数读取 =====================

def getParam(String name, String defaultVal) {
    try {
        def pa = build.getAction(hudson.model.ParametersAction.class)
        if (pa) {
            def p = pa.getParameter(name)
            if (p?.value) return p.value.toString()
        }
    } catch (ignored) {}
    return defaultVal
}

MONITOR_TYPE   = getParam("MONITOR_TYPE",   "pr")
MONITOR_BRANCH = getParam("MONITOR_BRANCH", "main")
REPO_URL       = getParam("REPO_URL",       "https://github.com/HuangPuStar/FenixAgent")
TARGET_JOB     = getParam("TARGET_JOB",     "PR-Pipeline-build")
GITHUB_TOKEN   = getParam("GITHUB_TOKEN",   "")
FORCE_RESET    = getParam("FORCE_RESET",    "false") == "true"

// 从 URL 解析 owner 和 name
// 支持: https://github.com/owner/repo  和  https://github.com/owner/repo.git
def repoPath = REPO_URL.replaceFirst(/^https?:\/\/[^\/]+\//, '').replaceFirst(/\.git$/, '')
def pathParts = repoPath.split('/')
REPO_OWNER = pathParts.length >= 2 ? pathParts[0] : ""
REPO_NAME  = pathParts.length >= 2 ? pathParts[1] : ""

if (!REPO_OWNER || !REPO_NAME) {
    throw new RuntimeException("Cannot parse owner/name from REPO_URL: ${REPO_URL}")
}

// 状态文件按模式+仓库隔离
def stateKey = MONITOR_TYPE == "branch" ? "branch-${MONITOR_BRANCH}" : "pr"
STATE_FILE = "${jenkins.model.Jenkins.instance.rootDir}/poll-state-${stateKey}-${REPO_OWNER}-${REPO_NAME}.json"

// GitHub API 代理列表（与 download_repo 同一套代理 + 直连兜底）
API_BASES = [
    "https://api.github.com",
    "https://ghfast.top/https://api.github.com",
    "https://ghproxy.net/https://api.github.com",
    "https://gh-proxy.com/https://api.github.com",
]

// ===================== 工具函数 =====================

/**
 * 带代理 fallback 的 HTTP GET
 * 依次尝试 API_BASES 中的每个代理，3 次重试，成功返回 JSON 解析结果
 */
def httpGetJson(String path) {
    for (base in API_BASES) {
        def url = base + path
        for (attempt in 1..3) {
            try {
                def conn = new URL(url).openConnection()
                conn.requestMethod = "GET"
                conn.connectTimeout = 10000
                conn.readTimeout = 15000
                conn.setRequestProperty("Accept", "application/vnd.github.v3+json")
                conn.setRequestProperty("User-Agent", "Jenkins-PR-Poller/1.0")
                if (GITHUB_TOKEN) {
                    conn.setRequestProperty("Authorization", "token ${GITHUB_TOKEN}")
                }

                if (conn.responseCode == 200) {
                    def body = conn.inputStream.text
                    def remaining = conn.getHeaderField("X-RateLimit-Remaining")
                    if (remaining) {
                        println "    Rate limit remaining: ${remaining}"
                    }
                    return new JsonSlurper().parseText(body)
                } else {
                    println "    HTTP ${conn.responseCode} from ${base} (attempt ${attempt})"
                }
            } catch (Exception e) {
                println "    Failed: ${base} (attempt ${attempt}): ${e.message}"
            }
            sleep(2000)
        }
        println "    Proxy ${base} exhausted, trying next..."
    }
    throw new RuntimeException("All API proxies failed for: ${path}")
}

/**
 * 触发 Jenkins Job 构建，传入参数
 */
def triggerBuild(Map params) {
    def jenkins = jenkins.model.Jenkins.instance
    def job = jenkins.getItem(TARGET_JOB)
    if (!job) {
        println "    ERROR: Job '${TARGET_JOB}' not found! Available jobs:"
        jenkins.items.each { println "      - ${it.name}" }
        return false
    }

    def paramsAction = new hudson.model.ParametersAction(
        params.collect { k, v -> new hudson.model.StringParameterValue(k, v ?: "") }
    )
    def causeAction = new hudson.model.CauseAction(
        new hudson.model.Cause.UpstreamCause(build)
    )
    job.scheduleBuild2(0, causeAction, paramsAction)
    return true
}

// ===================== PR 模式 =====================

def pollPRs(state) {
    println ""
    println ">>> Fetching open PRs..."
    def prs = httpGetJson("/repos/${REPO_OWNER}/${REPO_NAME}/pulls?state=open&sort=updated&direction=desc&per_page=30")
    println "    Found ${prs.size()} open PRs"

    def newState = [:]
    def triggered = 0
    def skipped = 0

    for (pr in prs) {
        def prId = pr.number.toString()
        def sha = pr.head.sha
        def branch = pr.head.ref
        def title = pr.title ?: ""
        def author = pr.user?.login ?: "unknown"
        def repoUrl = pr.head?.repo?.clone_url ?: ""

        newState[prId] = sha

        def prevSha = state[prId]
        if (prevSha == sha) {
            skipped++
            continue
        }

        println ""
        println ">>> Triggering: PR #${prId} — ${title}"
        println "    Branch: ${branch}"
        println "    Commit: ${sha.substring(0, Math.min(8, sha.size()))}"
        println "    Author: ${author}"
        println "    ${prevSha ? '(new commit)' : '(new PR)'}"

        def ok = triggerBuild([
            PR_BRANCH  : branch,
            PR_ID      : prId,
            PR_TITLE   : title,
            COMMIT_SHA : sha,
            AUTHOR     : author,
            APP_REPO   : repoUrl,
            APP_BRANCH : branch,
        ])

        if (ok) {
            triggered++
            println "    Build queued."
        } else {
            println "    Build trigger FAILED."
        }

        sleep(3000)
    }

    return [newState: newState, triggered: triggered, skipped: skipped]
}

// ===================== Branch 模式 =====================

def pollBranch(state) {
    println ""
    println ">>> Fetching latest commit on branch '${MONITOR_BRANCH}'..."
    def commits = httpGetJson("/repos/${REPO_OWNER}/${REPO_NAME}/commits?sha=${MONITOR_BRANCH}&per_page=1")

    if (!commits || commits.size() == 0) {
        println "    ERROR: No commits found on branch '${MONITOR_BRANCH}'"
        return [newState: state, triggered: 0, skipped: 0]
    }

    def commit = commits[0]
    def sha = commit.sha
    def message = commit.commit?.message ?: ""
    def author = commit.commit?.author?.name ?: commit.author?.login ?: "unknown"
    def branchKey = "branch:${MONITOR_BRANCH}"

    println "    Latest commit: ${sha.substring(0, Math.min(8, sha.size()))} by ${author}"
    println "    Message: ${message.take(80)}"

    def prevSha = state[branchKey]
    if (prevSha == sha) {
        println "    No change."
        return [newState: [(branchKey): sha], triggered: 0, skipped: 1]
    }

    println ""
    println ">>> Triggering: branch '${MONITOR_BRANCH}' has new commit"
    println "    ${prevSha ? '(new commit)' : '(first detection)'}"

    def ok = triggerBuild([
        PR_BRANCH  : MONITOR_BRANCH,
        PR_ID      : "0",
        PR_TITLE   : "Branch push: ${MONITOR_BRANCH} (${sha.substring(0, Math.min(8, sha.size()))})",
        COMMIT_SHA : sha,
        AUTHOR     : author,
        APP_REPO   : (REPO_URL.endsWith('.git') ? REPO_URL : REPO_URL + '.git'),
        APP_BRANCH : MONITOR_BRANCH,
    ])

    def triggered = ok ? 1 : 0
    if (ok) {
        println "    Build queued."
    } else {
        println "    Build trigger FAILED."
    }

    return [newState: [(branchKey): sha], triggered: triggered, skipped: 0]
}

// ===================== 主逻辑 =====================

println "=" * 60
println "GitHub Poll — ${new Date().format('yyyy-MM-dd HH:mm:ss')}"
println "Mode:   ${MONITOR_TYPE}"
println "Repo:   ${REPO_OWNER}/${REPO_NAME}"
if (MONITOR_TYPE == "branch") {
    println "Branch: ${MONITOR_BRANCH}"
}
println "Target: ${TARGET_JOB}"
if (FORCE_RESET) {
    println "Reset:  YES (state will be cleared)"
}
println "=" * 60

// 1. 读取上次状态
def state = [:]
def stateFile = new File(STATE_FILE)

// FORCE_RESET: 清除状态文件，以全新首次运行状态触发所有 PR/分支
if (FORCE_RESET && stateFile.exists()) {
    stateFile.delete()
    println ">>> FORCE_RESET: state file deleted, treating as first run"
}

if (stateFile.exists()) {
    state = new JsonSlurper().parseText(stateFile.text)
    println "State loaded: ${state.size()} entries"
} else {
    println "No state file, first run"
}

// 2. 按模式执行
def result
if (MONITOR_TYPE == "branch") {
    result = pollBranch(state)
} else {
    result = pollPRs(state)
}

// 3. 保存状态
stateFile.text = JsonOutput.toJson(result.newState)
println ""
println "=" * 60
println "Poll complete: triggered=${result.triggered}, skipped=${result.skipped}"
println "State saved: ${result.newState.size()} entries"
println "=" * 60
