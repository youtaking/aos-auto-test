pipeline {
    agent any

    parameters {
        string(name: 'PR_BRANCH',    description: 'PR 分支名（如 feat/xxx）',           defaultValue: 'main')
        string(name: 'PR_ID',        description: 'PR 编号（如 42）',                   defaultValue: '0')
        string(name: 'PR_TITLE',     description: 'PR 标题',                            defaultValue: 'manual build')
        string(name: 'COMMIT_SHA',   description: 'Commit SHA',                        defaultValue: 'unknown')
        string(name: 'AUTHOR',       description: '作者',                               defaultValue: 'unknown')
        string(name: 'TEST_REPO_BRANCH', description: 'aos-auto-test 分支',             defaultValue: 'feat/jenkins-pipeline')
    }

    environment {
        AUTOTEST_URL = "http://100.105.181.173:8111"
        APP_REPO     = "https://github.com/youtaking/FenixAgent.git"
        TEST_REPO    = "https://github.com/youtaking/aos-auto-test.git"
        PROJECT_NAME = "pr-env-${BUILD_NUMBER}"

        PORT_OFFSET = "${(BUILD_NUMBER.toInteger() % 10) * 3}"
        RCS_PORT    = "${30000 + PORT_OFFSET.toInteger()}"
        PG_PORT     = "${30001 + PORT_OFFSET.toInteger()}"
        LITE_PORT   = "${30002 + PORT_OFFSET.toInteger()}"
    }

    stages {
        stage('Init') {
            steps {
                sh '''
                    set +x
                    echo "############################################################"
                    echo "#                                                          #"
                    echo "#   PR Pipeline (Build) — Build #__BUILD_NUMBER__"
                    echo "#                                                          #"
                    echo "#   Project:    __PROJECT_NAME__"
                    echo "#   Branch:     __PR_BRANCH__"
                    echo "#   Author:     __AUTHOR__"
                    echo "#   RCS Port:   __RCS_PORT__ (host)"
                    echo "#   PG Port:    __PG_PORT__ (host)"
                    echo "#   LiteLLM:    __LITE_PORT__ (host)"
                    echo "#                                                          #"
                    echo "############################################################"

                    echo ""
                    echo ">>> Checking dependencies..."
                    if command -v python3 >/dev/null 2>&1; then
                        echo "    python3: $(python3 --version)"
                    elif command -v python >/dev/null 2>&1; then
                        echo "    python: $(python --version)"
                        echo '#!/bin/sh' > /usr/local/bin/python3
                        echo 'exec python "$@"' >> /usr/local/bin/python3
                        chmod +x /usr/local/bin/python3
                        echo "    python3 alias created -> python"
                    else
                        echo "    python not found, installing..."
                        apt-get update -qq && apt-get install -y -qq python3 > /dev/null 2>&1
                        echo "    python3 installed: $(python3 --version)"
                    fi

                    if ! command -v docker-compose >/dev/null 2>&1; then
                        echo "    docker-compose not found, installing..."
                        curl -sSL "https://github.com/docker/compose/releases/download/v2.29.2/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
                        chmod +x /usr/local/bin/docker-compose
                        echo "    docker-compose installed."
                    fi
                    echo "    docker-compose: $(docker-compose --version)"
                    echo ">>> Dependencies ready."
                '''.replace('__BUILD_NUMBER__', BUILD_NUMBER)
                  .replace('__PROJECT_NAME__', PROJECT_NAME)
                  .replace('__PR_BRANCH__', params.PR_BRANCH ?: 'main')
                  .replace('__AUTHOR__', params.AUTHOR ?: 'unknown')
                  .replace('__RCS_PORT__', RCS_PORT)
                  .replace('__PG_PORT__', PG_PORT)
                  .replace('__LITE_PORT__', LITE_PORT)
            }
        }

        stage('Clone Repos') {
            steps {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[1/7] Clone Repos — START"
                    echo "  Project:  __PROJECT_NAME__"
                    echo "  Branch:   __PR_BRANCH__"
                    echo "  Ports:    RCS=__RCS_PORT__  PG=__PG_PORT__  LiteLLM=__LITE_PORT__"
                    echo "============================================================"
                    echo ""
                    echo ">>> Cleaning previous workspace..."
                    rm -rf app autotest
                    mkdir -p app autotest

                    download_repo() {
                        local url="$1"
                        local output="$2"
                        local proxies="https://gh-proxy.com https://mirror.ghproxy.com https://ghfast.top https://ghproxy.net"
                        for proxy in $proxies ""; do
                            if [ -n "$proxy" ]; then
                                full_url="${proxy}/${url}"
                            else
                                full_url="$url"
                            fi
                            echo "    Trying: ${full_url}"
                            for i in 1 2 3; do
                                if curl --fail -SL --connect-timeout 10 --max-time 300 \\
                                  "${full_url}" -o "${output}" 2>/dev/null; then
                                    if [ -s "${output}" ] && tar tzf "${output}" > /dev/null 2>&1; then
                                        echo "    OK (proxy: ${proxy:-direct})"
                                        return 0
                                    fi
                                fi
                                echo "    Attempt $i failed, retrying..."
                                sleep 3
                            done
                            echo "    Proxy ${proxy:-direct} failed, trying next..."
                        done
                        echo "    ERROR: All proxies failed!"
                        return 1
                    }

                    echo ">>> Downloading FenixAgent (__PR_BRANCH__)..."
                    download_repo \\
                      "https://github.com/youtaking/FenixAgent/archive/refs/heads/__PR_BRANCH__.tar.gz" \\
                      /tmp/fenix.tar.gz
                    tar xzf /tmp/fenix.tar.gz --strip-components=1 -C app
                    rm -f /tmp/fenix.tar.gz
                    echo "    FenixAgent: $(ls app/ | wc -l) files/dirs in app/"

                    echo ">>> Downloading aos-auto-test (__TEST_REPO_BRANCH__)..."
                    download_repo \\
                      "https://github.com/youtaking/aos-auto-test/archive/refs/heads/__TEST_REPO_BRANCH__.tar.gz" \\
                      /tmp/autotest.tar.gz
                    tar xzf /tmp/autotest.tar.gz --strip-components=1 -C autotest
                    rm -f /tmp/autotest.tar.gz
                    echo "    aos-auto-test: $(ls autotest/ | wc -l) files/dirs in autotest/"

                    echo ""
                    echo "<<< [1/7] Clone Repos — DONE"
                '''.replace('__PR_BRANCH__', params.PR_BRANCH)
                  .replace('__TEST_REPO_BRANCH__', params.TEST_REPO_BRANCH)
                  .replace('__PROJECT_NAME__', PROJECT_NAME)
                  .replace('__RCS_PORT__', RCS_PORT)
                  .replace('__PG_PORT__', PG_PORT)
                  .replace('__LITE_PORT__', LITE_PORT)
            }
        }

        stage('Build Image') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[2/7] Build Image — START"
                    echo "  Runtime image:  __PROJECT_NAME__:__BUILD_NUMBER__"
                    echo "  Migrate image:  __PROJECT_NAME__-migrate:__BUILD_NUMBER__"
                    echo "============================================================"
                '''.replace('__PROJECT_NAME__', PROJECT_NAME)
                  .replace('__BUILD_NUMBER__', BUILD_NUMBER)

                dir('app') {
                    sh '''
                    set +x
                        echo ">>> Building runtime image (this may take a few minutes)..."
                        docker build -t __PROJECT_NAME__:__BUILD_NUMBER__ .
                        echo "    Runtime image built."

                        echo ">>> Building migrate image..."
                        docker build --target migrate -t __PROJECT_NAME__-migrate:__BUILD_NUMBER__ .
                        echo "    Migrate image built."

                        echo ""
                        echo "<<< [2/7] Build Image — DONE"
                        docker images | grep "__PROJECT_NAME__" || true
                    '''.replace('__PROJECT_NAME__', PROJECT_NAME)
                      .replace('__BUILD_NUMBER__', BUILD_NUMBER)
                }
            }
        }

        stage('Check Runner Images') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[2b] Check Runner Images — START"
                    echo "============================================================"

                    if docker image inspect test-runner:latest > /dev/null 2>&1; then
                        echo ">>> test-runner:latest already exists, skipping build."
                    else
                        echo ">>> test-runner:latest not found, building..."
                        docker build -t test-runner:latest -f autotest/Dockerfile.runner autotest/
                        echo "    test-runner:latest built."
                    fi

                    if docker image inspect unit-runner:latest > /dev/null 2>&1; then
                        echo ">>> unit-runner:latest already exists, skipping build."
                    else
                        echo ">>> unit-runner:latest not found, building..."
                        docker build -t unit-runner:latest -f autotest/Dockerfile.unit-runner autotest/
                        echo "    unit-runner:latest built."
                    fi

                    echo ""
                    echo "<<< [2b] Check Runner Images — DONE"
                '''
            }
        }

        stage('Resolve Tests') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[3/7] Resolve Tests — START"
                    echo "============================================================"
                '''
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                    set +x
                    set +e
                        echo ">>> Querying AutoTest API for test targets..."
                        curl -s -H "Authorization: Bearer $TOKEN" \\
                          __AUTOTEST_URL__/api/ci/resolve-tests > resolve_resp.json

                        echo ">>> API response:"
                        cat resolve_resp.json
                        echo ""

                        python3 -c "
import json
try:
    data = json.load(open('resolve_resp.json'))
    ids = data.get('data', {}).get('node_ids', [])
    if ids:
        fixed = [('/app/' + i if not i.startswith('/') else i) for i in ids]
        print(' '.join(fixed))
except Exception as e:
    import sys
    print(f'Parse error: {e}', file=sys.stderr)
" > test_targets.txt 2>/dev/null

                        if [ -s test_targets.txt ]; then
                            echo "    Source: AutoTest API"
                            echo "    Targets: $(cat test_targets.txt)"
                        elif [ -f autotest/tests/ci/cases.txt ]; then
                            echo "    Source: cases.txt (API unavailable)"
                            grep -v '^#' autotest/tests/ci/cases.txt | grep -v '^$' | sed 's|^tests/|/app/tests/|' | tr '\\n' ' ' > test_targets.txt
                            echo "    Targets: $(cat test_targets.txt)"
                        else
                            echo "    Source: fallback (all tests)"
                            echo "/app/tests/suites /app/tests/api_suites" > test_targets.txt
                            echo "    Targets: /app/tests/suites /app/tests/api_suites"
                        fi

                        echo ""
                        echo "<<< [3/7] Resolve Tests — DONE"
                    '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                }
            }
        }

        stage('Write Compose') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[4/7] Write Compose — START"
                    echo "============================================================"
                '''
                writeFile file: 'docker-compose.yml', text: '''
services:
  postgres:
    image: postgres:16-alpine
    privileged: true
    ports:
      - "__PG_PORT__:5432"
    environment:
      POSTGRES_USER: rcs
      POSTGRES_PASSWORD: rcs
      POSTGRES_DB: rcs
    volumes:
      - ./pg-init:/docker-entrypoint-initdb.d
      - ./seed-data.sql:/seed-data.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rcs"]
      interval: 5s
      timeout: 5s
      retries: 5

  migrate:
    image: __MIGRATE_IMAGE_TAG__
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgres://rcs:rcs@postgres:5432/rcs
    restart: "no"

  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "__LITE_PORT__:4000"
    environment:
      DATABASE_URL: postgresql://rcs:rcs@postgres:5432/litellm
      LITELLM_MASTER_KEY: sk-litellm-admin-dev-key
      STORE_MODEL_IN_DB: "True"

  rcs:
    image: __IMAGE_TAG__
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "__RCS_PORT__:3001"
    environment:
      DATABASE_URL: postgres://rcs:rcs@postgres:5432/rcs
      RCS_HOST: 0.0.0.0
      RCS_PORT: 3001
      RCS_API_KEYS: sk-rcs-dev-key
      RCS_SECRET_LITELLM_ADMIN_KEY: sk-litellm-admin-dev-key
      BETTER_AUTH_URL: http://localhost:3001
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3001/health"]
      interval: 10s
      timeout: 5s
      retries: 20

  test-runner:
    image: test-runner:latest
    depends_on:
      rcs:
        condition: service_healthy
    volumes:
      - __WORKSPACE__/autotest/tests:/app/tests
      - __WORKSPACE__/autotest/conftest.py:/app/conftest.py
    environment:
      FENIX_URL: http://rcs:3001
      FENIX_API_BASE_URL: http://rcs:3001
      HEADLESS: "true"
      PYTHONUNBUFFERED: "1"
    command: 'pytest __TEST_TARGETS__ -v --tb=short --base-url=http://rcs:3001 --json-report --json-report-file=/app/tests/results/report.json'

  unit-runner:
    image: unit-runner:latest
    volumes:
      - __WORKSPACE__/autotest/unit_tests:/app/tests
      - __WORKSPACE__/app:/app/fenix-source-parent:ro
'''.replace('__PG_PORT__', PG_PORT)
  .replace('__LITE_PORT__', LITE_PORT)
  .replace('__IMAGE_TAG__', "${PROJECT_NAME}:${BUILD_NUMBER}")
  .replace('__MIGRATE_IMAGE_TAG__', "${PROJECT_NAME}-migrate:${BUILD_NUMBER}")
  .replace('__RCS_PORT__', RCS_PORT)
  .replace('__WORKSPACE__', env.WORKSPACE.replace('/var/jenkins_home', '/opt/1panel/apps/jenkins/jenkins/data'))
  .replace('__TEST_TARGETS__', readFile('test_targets.txt').trim())

                sh '''
                    set +x
                    echo ">>> docker-compose.yml written:"
                    echo "    postgres  -> host port __PG_PORT__"
                    echo "    litellm   -> host port __LITE_PORT__"
                    echo "    rcs       -> host port __RCS_PORT__"
                    echo "    test targets: __TEST_TARGETS__"
                    echo ""
                    echo "<<< [4/7] Write Compose — DONE"
                '''.replace('__PG_PORT__', PG_PORT)
                  .replace('__LITE_PORT__', LITE_PORT)
                  .replace('__RCS_PORT__', RCS_PORT)
                  .replace('__TEST_TARGETS__', readFile('test_targets.txt').trim())
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[5/7] Deploy — START"
                    echo "  Project: __PROJECT_NAME__"
                    echo "============================================================"
                '''.replace('__PROJECT_NAME__', PROJECT_NAME)

                sh '''
                    set +x
                    echo ">>> Preparing pg-init scripts..."
                    mkdir -p pg-init
                    cat > pg-init/10-create-litellm.sh << 'INITEOF'
#!/bin/sh
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE litellm;
EOSQL
INITEOF
                    chmod +x pg-init/10-create-litellm.sh

                    echo ">>> Preparing seed data..."
                    rm -rf seed-data.sql
                    if [ -f autotest/data.sql ]; then
                      python3 -c "
lines = open('autotest/data.sql', encoding='utf-8').readlines()
out = []
skip = False
for line in lines:
    s = line.strip()
    if s.startswith('\\\\\\\\restrict') or s.startswith('\\\\\\\\unrestrict'):
        continue
    if 'COPY drizzle.__drizzle_migrations' in line:
        skip = True
        continue
    if skip and s == '\\\\\\\\.':
        skip = False
        continue
    if skip:
        continue
    out.append(line)
open('seed-data.sql', 'w', encoding='utf-8').writelines(out)
"
                      echo "    seed-data.sql ready ($(wc -l < seed-data.sql) lines)."
                    else
                      echo "    WARNING: autotest/data.sql not found, creating empty seed."
                      echo "-- No seed data" > seed-data.sql
                    fi

                    echo ">>> Starting postgres..."
                    docker-compose -p __PROJECT_NAME__ up -d postgres

                    echo ">>> Waiting for postgres to be ready..."
                    for i in $(seq 1 30); do
                        if docker-compose -p __PROJECT_NAME__ exec -T postgres pg_isready -U rcs > /dev/null 2>&1; then
                            echo "    Postgres is ready! (after ~$((i*2))s)"
                            break
                        fi
                        if [ $i -eq 30 ]; then
                            echo "    ERROR: Postgres did not become ready in 60s!"
                            docker-compose -p __PROJECT_NAME__ logs postgres
                            exit 1
                        fi
                        sleep 2
                    done

                    echo ">>> Running database migration..."
                    docker-compose -p __PROJECT_NAME__ run --rm --no-deps migrate
                    echo "    Migration complete."

                    echo ">>> Importing seed data..."
                    if grep -q '^[^-]' seed-data.sql 2>/dev/null; then
                        docker-compose -p __PROJECT_NAME__ exec -T postgres \
                          psql -U rcs -d rcs -v ON_ERROR_STOP=1 -f /seed-data.sql
                        echo "    Seed data imported."
                    else
                        echo "    No seed data to import, skipping."
                    fi

                    echo ">>> Starting litellm + rcs..."
                    docker-compose -p __PROJECT_NAME__ up -d litellm rcs

                    echo ">>> Waiting for RCS health check (max 10min)..."
                    echo "    Health URL: http://100.105.114.178:__RCS_PORT__/health"
                    for i in $(seq 1 120); do
                        if curl -sf http://100.105.114.178:__RCS_PORT__/health > /dev/null 2>&1; then
                            echo "    RCS is healthy! (after ~$((i*5))s)"
                            echo ""
                            echo "<<< [5/7] Deploy — DONE"
                            exit 0
                        fi
                        if [ $((i % 10)) -eq 0 ]; then
                            echo "    --- Attempt $i/120 (~$((i*5))s) - RCS logs ---"
                            docker-compose -p __PROJECT_NAME__ logs --tail=10 rcs 2>&1 || true
                        fi
                        sleep 5
                    done
                    echo "    ERROR: RCS health check timeout after 600s! Last logs:"
                    docker-compose -p __PROJECT_NAME__ logs --tail=30 rcs 2>&1 || true
                    exit 1
                '''.replace('__PROJECT_NAME__', PROJECT_NAME)
                  .replace('__RCS_PORT__', RCS_PORT)
            }
        }

        stage('Create Pipeline Record') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[6/7] Create Pipeline Record — START"
                    echo "  AutoTest URL: __AUTOTEST_URL__"
                    echo "  Branch:       __PR_BRANCH__"
                    echo "============================================================"
                '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                  .replace('__PR_BRANCH__', params.PR_BRANCH ?: 'main')

                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                    set +x
                        echo ">>> Sending pipeline record to AutoTest API..."
                        RESP=$(curl -s -w "\\n%{http_code}" -X POST __AUTOTEST_URL__/api/pipelines \\
                          -H "Authorization: Bearer $TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d '{
                            "pr_id": __PR_ID__,
                            "pr_title": "__PR_TITLE__",
                            "commit_sha": "__COMMIT_SHA__",
                            "branch": "__PR_BRANCH__",
                            "repo_url": "__APP_REPO__",
                            "author": "__AUTHOR__",
                            "target_url": "http://localhost:__RCS_PORT__",
                            "build_info": {
                              "jenkins_url": "__BUILD_URL__",
                              "build_number": __BUILD_NUMBER__,
                              "docker_image": "__IMAGE_TAG__",
                              "rcs_port": __RCS_PORT__,
                              "pg_port": __PG_PORT__,
                              "litellm_port": __LITE_PORT__
                            }
                          }')

                        HTTP_CODE=$(echo "$RESP" | tail -1)
                        BODY=$(echo "$RESP" | sed '$d')
                        echo "$BODY" > pipeline.json

                        echo ">>> API response (HTTP $HTTP_CODE):"
                        echo "$BODY"

                        if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "201" ]; then
                            echo ""
                            echo "    ERROR: AutoTest API returned HTTP $HTTP_CODE"
                            echo "    Pipeline record creation failed. Check if the API endpoint exists."
                            echo "<<< [6/7] Create Pipeline Record — FAILED"
                            exit 1
                        fi

                        PIPELINE_ID=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('id',''))" < pipeline.json)
                        if [ -z "$PIPELINE_ID" ]; then
                            echo ""
                            echo "    ERROR: API response missing 'data.id'"
                            echo "<<< [6/7] Create Pipeline Record — FAILED"
                            exit 1
                        fi

                        echo "    Pipeline ID: $PIPELINE_ID"
                        echo ""
                        echo "<<< [6/7] Create Pipeline Record — DONE"
                    '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                      .replace('__PR_ID__', params.PR_ID ?: '0')
                      .replace('__PR_TITLE__', params.PR_TITLE ?: 'manual build')
                      .replace('__COMMIT_SHA__', params.COMMIT_SHA ?: 'unknown')
                      .replace('__PR_BRANCH__', params.PR_BRANCH ?: 'main')
                      .replace('__APP_REPO__', APP_REPO)
                      .replace('__AUTHOR__', params.AUTHOR ?: 'unknown')
                      .replace('__RCS_PORT__', RCS_PORT)
                      .replace('__BUILD_URL__', env.BUILD_URL ?: '')
                      .replace('__BUILD_NUMBER__', BUILD_NUMBER)
                      .replace('__IMAGE_TAG__', "${PROJECT_NAME}:${BUILD_NUMBER}")
                      .replace('__PG_PORT__', PG_PORT)
                      .replace('__LITE_PORT__', LITE_PORT)
                }
            }
        }

        stage('Run Unit Tests') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "Run Unit Tests — START"
                    echo "============================================================"
                '''

                // 1. 获取 PIPELINE_ID 并通知后端"单元测试开始"
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                    set +x
                        PIPELINE_ID=""
                        if [ -f pipeline.json ]; then
                            PIPELINE_ID=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('id', ''))
except:
    print('')
" < pipeline.json)
                        fi
                        echo "$PIPELINE_ID" > .pipeline_id

                        if [ -n "$PIPELINE_ID" ]; then
                            echo ">>> Notifying backend: unit tests starting (pipeline_id=$PIPELINE_ID)..."
                            START_RESP=$(curl -s -X POST __AUTOTEST_URL__/api/unit-tests/runs/start \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d "{\\"pipeline_id\\": $PIPELINE_ID}")
                            echo "$START_RESP"
                            UNIT_RUN_ID=$(echo "$START_RESP" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('data', {}).get('run_id', ''))
except:
    print('')
" 2>/dev/null)
                            echo "    Unit run_id: $UNIT_RUN_ID"
                            echo "$UNIT_RUN_ID" > .unit_run_id
                        else
                            echo "    WARNING: No pipeline ID, skipping start notification."
                            echo "" > .unit_run_id
                        fi
                    '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                }

                // 2. 运行单元测试（失败不阻塞 pipeline）
                sh '''
                    set +x
                    echo ">>> Starting unit-runner (bun:test)..."
                '''
                sh "docker-compose -p ${PROJECT_NAME} up unit-runner || true"

                // 3. 收集并上传结果（带上 run_id 更新已有记录）
                sh '''
                    set +x
                    echo ">>> Copying unit-junit.xml from volume..."
                    cp __WORKSPACE__/autotest/unit_tests/results/unit-junit.xml unit-junit.xml 2>/dev/null || true
                '''.replace('__WORKSPACE__', env.WORKSPACE.replace('/var/jenkins_home', '/opt/1panel/apps/jenkins/jenkins/data'))

                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                    set +x
                        UNIT_RUN_ID=$(cat .unit_run_id 2>/dev/null || echo "")
                        PIPELINE_ID=$(cat .pipeline_id 2>/dev/null || echo "")

                        if [ -f unit-junit.xml ] && [ -n "$PIPELINE_ID" ]; then
                            echo ">>> Uploading unit test results..."
                            python3 -c "
import json, sys
xml_content = open('unit-junit.xml', 'r', encoding='utf-8').read()
run_id = '$UNIT_RUN_ID'.strip()
payload = {'pipeline_id': int($PIPELINE_ID), 'junit_xml': xml_content}
if run_id:
    payload['run_id'] = int(run_id)
open('unit-upload.json', 'w', encoding='utf-8').write(json.dumps(payload))
"
                            curl -s -X POST __AUTOTEST_URL__/api/unit-tests/results \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d @unit-upload.json
                            echo ""
                            echo "    Unit test results uploaded."
                        else
                            UNIT_RUN_ID=$(cat .unit_run_id 2>/dev/null || echo "")
                            if [ ! -f unit-junit.xml ] && [ -n "$UNIT_RUN_ID" ]; then
                                echo "    WARNING: unit-junit.xml not found, marking unit run as error..."
                                curl -s -X PUT __AUTOTEST_URL__/api/unit-tests/runs/\${UNIT_RUN_ID}/status \\
                                  -H "Authorization: Bearer $TOKEN" \\
                                  -H "Content-Type: application/json" \\
                                  -d '{"status": "error"}'
                                echo ""
                            fi
                            [ -z "$PIPELINE_ID" ] && echo "    WARNING: No pipeline ID, skipping unit upload."
                        fi
                        exit 0
                    '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                }

                sh '''
                    set +x
                    echo ""
                    echo "<<< Run Unit Tests — DONE"
                '''
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[7/7] Run Tests — START"
                    echo "============================================================"
                '''

                // 通知后端：集成测试开始
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                    set +x
                        PIPELINE_ID=$(cat .pipeline_id 2>/dev/null || echo "")
                        if [ -n "$PIPELINE_ID" ]; then
                            echo ">>> Notifying backend: integration tests starting (pipeline_id=$PIPELINE_ID)..."
                            curl -s -X PUT __AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/status \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d '{"status": "running"}'
                            echo ""
                        fi
                    '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                }

                sh '''
                    set +x
                    echo ">>> Starting test-runner (streaming logs)..."
                '''
                sh "docker-compose -p ${PROJECT_NAME} logs -f test-runner &"
                sh "docker-compose -p ${PROJECT_NAME} up test-runner || true"
                sh '''
                    set +x
                    echo ""
                    echo "<<< [7/7] Run Tests — DONE"
                '''
            }
        }

        stage('Collect Results') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "Collect Results — START"
                    echo "============================================================"
                    echo ">>> Copying report.json from volume..."
                    cp __WORKSPACE__/autotest/tests/results/report.json report.json 2>/dev/null || true
                '''.replace('__WORKSPACE__', env.WORKSPACE.replace('/var/jenkins_home', '/opt/1panel/apps/jenkins/jenkins/data'))

                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                    set +x
                        PIPELINE_ID=""
                        if [ -f pipeline.json ]; then
                            PIPELINE_ID=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('id', ''))
except:
    print('')
" < pipeline.json)
                        fi

                        if [ -f report.json ] && [ -n "$PIPELINE_ID" ]; then
                            echo ">>> Uploading API/UI results to AutoTest API (pipeline_id=$PIPELINE_ID)..."
                            curl -s -X POST __AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/results \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d @report.json
                            echo ""
                            echo "    API/UI Results uploaded."
                        else
                            [ ! -f report.json ] && echo "    WARNING: report.json not found."
                            [ -z "$PIPELINE_ID" ] && echo "    WARNING: No valid pipeline ID, skipping result upload."
                        fi
                        echo ""
                        echo "<<< Collect Results — DONE"
                    '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                }
            }
        }
    }

    post {
        success {
            echo "============================================================"
            echo "PIPELINE RESULT: SUCCESS"
            echo "============================================================"
            withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                sh '''
                    set +x
                    PIPELINE_ID=""
                    if [ -f pipeline.json ]; then
                        PIPELINE_ID=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('id', ''))
except:
    print('')
" < pipeline.json)
                    fi
                    if [ -n "$PIPELINE_ID" ]; then
                        echo ">>> Updating pipeline status to 'passed'..."
                        curl -s -X PUT __AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/status \\
                          -H "Authorization: Bearer $TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d '{"status": "passed"}'
                    else
                        echo "    No valid pipeline ID, skipping status update."
                    fi
                '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
            }
        }
        failure {
            echo "============================================================"
            echo "PIPELINE RESULT: FAILURE"
            echo "============================================================"
            withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                sh '''
                    set +x
                    PIPELINE_ID=""
                    if [ -f pipeline.json ]; then
                        PIPELINE_ID=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('id', ''))
except:
    print('')
" < pipeline.json)
                    fi
                    if [ -n "$PIPELINE_ID" ]; then
                        echo ">>> Updating pipeline status to 'failed'..."
                        curl -s -X PUT __AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/status \\
                          -H "Authorization: Bearer $TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d '{"status": "failed"}'
                    else
                        echo "    No valid pipeline ID, skipping status update."
                    fi
                '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
            }
        }
        always {
            echo ""
            echo "============================================================"
            echo "Cleanup — START"
            echo "============================================================"
            sh '''
                    set +x
                echo ">>> Stopping and removing containers..."
                docker-compose -p __PROJECT_NAME__ down -v || true
                echo ">>> Images kept for debug use:"
                echo "    __IMAGE_TAG__"
                echo "    __MIGRATE_IMAGE_TAG__"
                echo ""
                echo "<<< Cleanup — DONE"
                echo ""
                echo "============================================================"
                echo "Pipeline finished. Build #${BUILD_NUMBER}"
                echo "============================================================"
            '''.replace('__PROJECT_NAME__', PROJECT_NAME)
              .replace('__IMAGE_TAG__', "${PROJECT_NAME}:${BUILD_NUMBER}")
              .replace('__MIGRATE_IMAGE_TAG__', "${PROJECT_NAME}-migrate:${BUILD_NUMBER}")
        }
    }
}
