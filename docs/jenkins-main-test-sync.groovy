// main-test-sync：每日批量比对 FenixAgent main 与 baseline，按影响面同步 unit/API/E2E 用例。
// COMMIT_SHA 留空时自动解析 refs/heads/main 的最新提交。
// 只生成 sync/main-<sha8> 分支 + GitLab Draft MR + GitHub 镜像分支，绝不自动合并。
//
// 逐提交触发会在大模型上调起大量重复分析（每月约 69 次、~$128），改为每天一次批量：
// baseline..main 的全部改动一次分析完，成本约 30 次/月。

def NOTIFY_WECOM_ON() { return params.NOTIFY_WECOM != null ? params.NOTIFY_WECOM : true }
def DRY_RUN_ON()     { return params.DRY_RUN != null ? params.DRY_RUN : true }

pipeline {
    agent any

    options {
        // 定时与手动同时触发会各自 clone/push，互相覆盖
        disableConcurrentBuilds()
    }

    triggers {
        // Jenkins 是 UTC，H 19 = 北京时间次日 03:xx（H 打散分钟，避免整点堆积）
        cron('H 19 * * *')
    }

    parameters {
        string(name: 'COMMIT_SHA', defaultValue: '', description: '目标提交；留空自动取 refs/heads/main 最新提交')
        string(name: 'BASE_SHA',   defaultValue: '', description: '对比基线；留空读 sync/baseline.json 的 main_sha')
        string(name: 'SYNC_MODEL', defaultValue: 'deepseek-v4-flash-anthropic', description: 'LiteLLM 模型别名（Models 页的 model_name）')
        booleanParam(name: 'DRY_RUN', defaultValue: false, description: '勾选则只生成补丁不发布；默认关（会自动开 Draft MR，但绝不自动合并）')
        booleanParam(name: 'NOTIFY_WECOM', defaultValue: true, description: '发送企业微信通知')
    }

    environment {
        FENIX_REPO_CLONE = 'https://github.com/HuangPuStar/FenixAgent.git'
        GITLAB_HTTPS     = 'https://gitlab.pazhoulab-huangpu.com/aos-test/aos-auto-test.git'
        GITLAB_API       = 'https://gitlab.pazhoulab-huangpu.com/api/v4/projects/aos-test%2Faos-auto-test'
        ANTHROPIC_BASE_URL_ENV = 'http://100.105.114.178:34000/litellm'
    }

    stages {
        stage('Init') {
            steps {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "main-test-sync"
                    echo "  commit: __HEAD__"
                    echo "  base:   __BASE__"
                    echo "  dry:    __DRY__"
                    echo "============================================================"
                '''.replace('__HEAD__', params.COMMIT_SHA ?: '(resolve latest main)')
                  .replace('__BASE__', params.BASE_SHA ?: '(from baseline)')
                  .replace('__DRY__', DRY_RUN_ON().toString())

                script {
                    if (!params.SYNC_MODEL?.trim()) {
                        // 凭证 / 模型别名尚未配置时只跳过，不刷失败构建
                        env.SYNC_STATE = 'unconfigured'
                        currentBuild.displayName = "#${env.BUILD_NUMBER} [SYNC] skipped: SYNC_MODEL 未配置"
                        currentBuild.result = 'NOT_BUILT'
                    } else {
                        env.SYNC_STATE = 'pending'
                    }
                }
            }
        }

        stage('Clone Test Repo') {
            when { expression { env.SYNC_STATE == 'pending' } }
            steps {
                withCredentials([string(credentialsId: 'gitlab-read-token', variable: 'GL_READ_TOKEN')]) {
                sh '''
                    set +x
                    echo ">>> Cloning aos-auto-test (main)..."
                    rm -rf autotest
                    GL_AUTH=$(printf 'oauth2:%s' "$GL_READ_TOKEN" | base64 | tr -d '\\n')
                    git -c http.extraHeader="Authorization: Basic ${GL_AUTH}" \
                      clone --depth 50 -b main "__GITLAB__" autotest
                    echo "    HEAD: $(git -C autotest rev-parse --short HEAD)"

                    # 未指定 COMMIT_SHA 时取 main 最新提交（每日批量模式）
                    if [ -n "__HEAD_PARAM__" ]; then
                        HEAD_SHA="__HEAD_PARAM__"
                    else
                        HEAD_SHA=""
                        for proxy in "https://ghfast.top/" "" "https://ghproxy.net/"; do
                            HEAD_SHA=$(GIT_TERMINAL_PROMPT=0 timeout 60 \
                              git ls-remote "${proxy}__FENIX__" refs/heads/main 2>/dev/null | cut -f1)
                            [ -n "$HEAD_SHA" ] && break
                            sleep 2
                        done
                        [ -n "$HEAD_SHA" ] || { echo "    ERROR: 无法解析 main 最新提交"; exit 1; }
                    fi
                    echo "$HEAD_SHA" > .resolved_head
                    echo "    TARGET: $(echo "$HEAD_SHA" | cut -c1-8)"

                    if [ -n "__BASE_PARAM__" ]; then
                        BASE_SHA="__BASE_PARAM__"
                    else
                        BASE_SHA=$(python3 -c "import json;print(json.load(open('autotest/sync/baseline.json',encoding='utf-8'))['main_sha'])")
                    fi
                    echo "$BASE_SHA" > .base_sha
                    echo "    BASE: $(echo "$BASE_SHA" | cut -c1-8)"
                '''.replace('__GITLAB__', env.GITLAB_HTTPS)
                   .replace('__BASE_PARAM__', params.BASE_SHA ?: '')
                   .replace('__HEAD_PARAM__', params.COMMIT_SHA ?: '')
                   .replace('__FENIX__', env.FENIX_REPO_CLONE)
                }
            }
        }

        stage('Idempotency Check') {
            when { expression { env.SYNC_STATE == 'pending' } }
            steps {
                withCredentials([string(credentialsId: 'gitlab-read-token', variable: 'GL_TOKEN')]) {
                sh '''
                    set +x
                    BASE_SHA=$(cat .base_sha)
                    HEAD_SHA=$(cat .resolved_head)
                    SHA8=$(echo "$HEAD_SHA" | cut -c1-8)
                    echo "$SHA8" > .sha8
                    echo "$HEAD_SHA" > .head_sha

                    if [ "$BASE_SHA" = "$HEAD_SHA" ]; then
                        echo ">>> baseline 已等于目标提交，无需同步"
                        echo "empty" > .sync_state
                        exit 0
                    fi

                    GL_AUTH=$(printf 'oauth2:%s' "$GL_TOKEN" | base64 | tr -d '\\n')
                    if git -c http.extraHeader="Authorization: Basic ${GL_AUTH}" ls-remote --heads "__GITLAB__" "refs/heads/sync/main-$SHA8" | grep -q .; then
                        echo ">>> 分支 sync/main-$SHA8 已存在，跳过"
                        echo "skip" > .sync_state
                        exit 0
                    fi

                    MR=$(curl -s -H "PRIVATE-TOKEN: ${GL_TOKEN}" "__GITLAB_API__/merge_requests?source_branch=sync/main-$SHA8&state=opened")
                    if echo "$MR" | grep -q '"iid"'; then
                        echo ">>> 已存在 Draft MR，跳过"
                        echo "skip" > .sync_state
                        exit 0
                    fi

                    echo "run" > .sync_state
                '''.replace('__GITLAB__', env.GITLAB_HTTPS)
                   .replace('__GITLAB_API__', env.GITLAB_API)
                }
                script {
                    if (fileExists('.sync_state')) {
                        def state = readFile('.sync_state').trim()
                        env.SYNC_STATE = state
                        if (state == 'skip') {
                            currentBuild.displayName = "#${env.BUILD_NUMBER} [SYNC] already exists"
                        } else if (state == 'empty') {
                            currentBuild.displayName = "#${env.BUILD_NUMBER} [SYNC] up to date"
                        }
                    }
                }
            }
        }

        stage('Clone FenixAgent') {
            when { expression { env.SYNC_STATE == 'run' } }
            steps {
                sh '''
                    set +x
                    HEAD_SHA=$(cat .head_sha)
                    echo ">>> Cloning FenixAgent main and checking out $(echo "$HEAD_SHA" | cut -c1-8)..."
                    ok=0
                    # 单次尝试 240s 上限：代理挂起时不会无限期阻塞整个构建
                    # 实测 ghfast.top 稳定 10s 左右，直连时快时挂（曾 240s 超时），gh-proxy 会挂死
                    for proxy in "https://ghfast.top/" "" "https://ghproxy.net/" "https://gh-proxy.com/"; do
                        rm -rf fenix
                        echo "    Trying: ${proxy:-direct}"
                        if GIT_TERMINAL_PROMPT=0 timeout 240 git clone --single-branch --branch main \
                             "${proxy}__FENIX__" fenix 2>/dev/null; then
                            ok=1
                            break
                        fi
                        echo "    failed or timed out"
                        sleep 3
                    done
                    [ "$ok" = "1" ] || { echo "    ERROR: clone FenixAgent failed"; exit 1; }
                    git -C fenix checkout --detach "$HEAD_SHA"
                    echo "    checked out: $(git -C fenix rev-parse --short HEAD)"
                '''.replace('__FENIX__', env.FENIX_REPO_CLONE)
            }
        }

        stage('Sync In Container') {
            when { expression { env.SYNC_STATE == 'run' } }
            steps {
                sh 'mkdir -p artifacts'
                withCredentials([string(credentialsId: 'litellm-main-test-sync-key', variable: 'LITELLM_KEY')]) {
                sh '''
                    set +x
                    BASE_SHA=$(cat .base_sha)
                    HEAD_SHA=$(cat .head_sha)
                    if [ "__DRY__" = "true" ]; then DRY_FLAG=true; else DRY_FLAG=false; fi
                    set +e
                    # docker 守护进程在宿主机解析 -v 路径，而 WORKSPACE 是容器内路径，需换成宿主机路径
                    WS_HOST=$(echo "$WORKSPACE" | sed 's|^/var/jenkins_home|/opt/1panel/apps/jenkins/jenkins/data|')
                    # fenix 挂载可写：单测要 import main 源码，必须在仓库根 bun install 生成 node_modules。
                    # 源码不被改动由 entrypoint 的 git status 校验兜底（任何改动即失败）。
                    # 入口脚本从仓库挂载，工作区 checkout 无执行位，显式用 sh 调起
                    docker run --rm --entrypoint /bin/sh \
                      -v "$WS_HOST/fenix:/workspace" \
                      -v "$WS_HOST/autotest:/repo" \
                      -v "$WS_HOST/autotest/entrypoint-test-sync.sh:/app/entrypoint-test-sync.sh:ro" \
                      -v "$WS_HOST/artifacts:/artifacts" \
                      -e BASE_SHA="$BASE_SHA" \
                      -e HEAD_SHA="$HEAD_SHA" \
                      -e DRY_RUN="$DRY_FLAG" \
                      -e MAX_SYNC_TURNS=40 \
                      -e IS_SANDBOX=1 \
                      -e ANTHROPIC_BASE_URL="__BASE_URL__" \
                      -e ANTHROPIC_AUTH_TOKEN="$LITELLM_KEY" \
                      -e ANTHROPIC_MODEL="__MODEL__" \
                      -e ANTHROPIC_DEFAULT_OPUS_MODEL="__MODEL__" \
                      -e ANTHROPIC_DEFAULT_SONNET_MODEL="__MODEL__" \
                      -e ANTHROPIC_DEFAULT_HAIKU_MODEL="__MODEL__" \
                      -e ANTHROPIC_SMALL_FAST_MODEL="__MODEL__" \
                      test-sync-runner:latest /app/entrypoint-test-sync.sh
                    SYNC_EXIT=$?
                    set -e
                    echo "$SYNC_EXIT" > .sync_exit
                    echo ">>> sync exit code: $SYNC_EXIT"
                    case "$SYNC_EXIT" in
                        0) echo "run" > .sync_result ;;
                        10) echo "empty" > .sync_result ;;
                        11) echo "policy" > .sync_result ;;
                        12) echo "checks" > .sync_result ;;
                        13) echo "ai" > .sync_result ;;
                        14) echo "nochange" > .sync_result ;;
                        15) echo "review" > .sync_result ;;
                        *) echo "error" > .sync_result ;;
                    esac
                '''.replace('__DRY__', DRY_RUN_ON().toString())
                   .replace('__BASE_URL__', env.ANTHROPIC_BASE_URL_ENV)
                   .replace('__MODEL__', params.SYNC_MODEL.trim())
                }
                script {
                    def result = fileExists('.sync_result') ? readFile('.sync_result').trim() : 'error'
                    if (result == 'empty') {
                        env.SYNC_STATE = 'empty'
                        currentBuild.displayName = "#${env.BUILD_NUMBER} [SYNC] impact empty"
                    } else if (result == 'nochange') {
                        env.SYNC_STATE = 'empty'
                        currentBuild.displayName = "#${env.BUILD_NUMBER} [SYNC] no changes"
                    } else if (result == 'run') {
                        env.SYNC_STATE = 'ready'
                    } else {
                        // 标记失败但不抛异常：否则后续 post 里的企微通知会被跳过
                        env.SYNC_STATE = result
                        currentBuild.result = 'FAILURE'
                        echo "同步失败：${result}（详见 artifacts/）"
                    }
                }
            }
        }

        stage('Publish') {
            when { expression { env.SYNC_STATE == 'ready' && !DRY_RUN_ON() } }
            steps {
                withCredentials([
                    string(credentialsId: 'gitlab-write-token', variable: 'GL_WRITE_TOKEN'),
                    usernamePassword(credentialsId: 'mygithub-token', usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')
                ]) {
                sh '''
                    set +x
                    SHA8=$(cat .sha8)
                    BRANCH="sync/main-$SHA8"

                    cd autotest
                    git config user.email "ci@autotest.local"
                    git config user.name "autotest-ci"
                    git checkout -b "$BRANCH"
                    git add unit_tests tests docs/手工用例 sync/baseline.json
                    if git diff --cached --quiet; then
                        echo ">>> 没有可提交的改动"
                        echo "nochange" > ../.publish_result
                        exit 0
                    fi
                    git commit -m "test: 同步 main $SHA8 变更到测试用例"
                    GL_AUTH=$(printf 'oauth2:%s' "$GL_WRITE_TOKEN" | base64 | tr -d '\\n')
                    git -c http.extraHeader="Authorization: Basic ${GL_AUTH}" push origin "$BRANCH"

                    git remote add github "https://github.com/youtaking/aos-auto-test.git" || true
                    GH_AUTH=$(printf 'x-access-token:%s' "$GH_TOKEN" | base64 | tr -d '\\n')
                    git -c http.extraHeader="AUTHORIZATION: basic ${GH_AUTH}" push github "$BRANCH"
                    cd ..

                    BASE_SHA=$(cat .base_sha)
                    HEAD_SHA=$(cat .head_sha)
                    DESC=$(printf '自动同步 FenixAgent main `%s` 的测试用例。\\n\\n- BASE: `%s`\\n- 影响面与改动：见构建产物 impact.json / changes.json\\n- Claude Code 生成并复核，人工 Review 后再合并。' "$HEAD_SHA" "$BASE_SHA")
                    curl -s -X POST -H "PRIVATE-TOKEN: ${GL_WRITE_TOKEN}" \
                      --data-urlencode "source_branch=$BRANCH" \
                      --data-urlencode "target_branch=main" \
                      --data-urlencode "title=Draft: 同步 main $SHA8 的测试用例" \
                      --data-urlencode "description=$DESC" \
                      "__GITLAB_API__/merge_requests" > artifacts/mr.json
                    python3 -c "import json;d=json.load(open('artifacts/mr.json',encoding='utf-8'));print(d.get('web_url') or d)" > artifacts/mr_url.txt || true
                    echo ">>> MR: $(cat artifacts/mr_url.txt 2>/dev/null)"
                    echo "published" > .publish_result
                '''.replace('__GITLAB_API__', env.GITLAB_API)
                }
            }
        }

    }

    post {
        always {
            archiveArtifacts artifacts: 'artifacts/**', allowEmptyArchive: true

            script {
                // 只在有补丁 / 失败 / 需要人看时通知：“已是最新”“已存在分支”不打扰
                def st = env.SYNC_STATE ?: 'error'
                if (NOTIFY_WECOM_ON() && st != 'unconfigured' && st != 'empty' && st != 'skip') {
                    withCredentials([string(credentialsId: 'wecom-webhook', variable: 'WECOM_WEBHOOK')]) {
                    sh '''
                        set +x
                        python3 - <<'PY'
import json, os

def read(path, default=''):
    try:
        return open(path, encoding='utf-8').read().strip()
    except Exception:
        return default

state = read('.sync_state', 'unknown')
result = read('.sync_result', '')
build_url = os.environ.get('BUILD_URL', '')
sha = read('.head_sha', '')
sha8 = read('.sha8', sha[:8])
base = read('.base_sha', '')
dry = '__DRY__' == 'true'
mr = read('artifacts/mr_url.txt', '')

try:
    impact = json.load(open('artifacts/impact.json', encoding='utf-8'))
    auto = impact.get('auto', {})
    stat = f"影响面 {len(impact.get('rules', {}))} 条规则：unit {len(auto.get('unit', []))} / api {len(auto.get('api', []))} / e2e {len(auto.get('e2e', []))}；未映射 {len(impact.get('unmapped', []))}"
except Exception:
    stat = '无影响面数据'

try:
    changes = json.load(open('artifacts/changes.json', encoding='utf-8'))
    changed = f"AI 改动 {len(changes.get('files', []))} 个文件"
except Exception:
    changed = '无改动数据'

publish = read('.publish_result', '')

if state == 'skip':
    icon, title = '⏭️', '已存在同步分支/MR，跳过'
elif state == 'empty':
    icon, title = '✅', '已是最新（无需同步）'
elif state == 'ready' or result:
    if dry:
        icon, title = '🧪', '同步补丁已生成（DRY RUN）'
    elif publish == 'published':
        icon, title = '✅', '已提交 Draft MR'
    elif publish == 'nochange':
        icon, title = '✅', '无实际改动'
    else:
        icon, title = '❌', '发布失败'
else:
    icon, title = '❌', '同步失败'

lines = [
    f'### {icon} main-test-sync {title}',
    f'> commit: `{sha8}`',
    f'> base: `{base[:8]}`',
    f'> {stat}',
    f'> {changed}',
]
if mr:
    lines.append(f'> [Draft MR]({mr})')
if build_url:
    lines.append(f'> [Jenkins 构建日志]({build_url})')
payload = {'msgtype': 'markdown', 'markdown': {'content': chr(10).join(lines)}}
open('wecom_sync_payload.json', 'w', encoding='utf-8').write(json.dumps(payload, ensure_ascii=False))
PY
                        curl -s -X POST "$WECOM_WEBHOOK" -H "Content-Type: application/json" -d @wecom_sync_payload.json || true
                    '''.replace('__DRY__', DRY_RUN_ON().toString())
                    }
                }
            }

            sh '''
                rm -rf fenix artifacts autotest
                rm -f .base_sha .head_sha .resolved_head .sha8 .sync_state .sync_result .sync_exit .publish_result wecom_sync_payload.json
            '''
        }
    }
}
