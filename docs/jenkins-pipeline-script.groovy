pipeline {
    agent any

    environment {
        AUTOTEST_URL = "http://100.105.181.173:8000"
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
                    echo "#   PR Pipeline — Build #__BUILD_NUMBER__"
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

                    echo ">>> Downloading FenixAgent (__PR_BRANCH__)..."
                    curl -SL "https://gh-proxy.com/https://github.com/youtaking/FenixAgent/archive/refs/heads/__PR_BRANCH__.tar.gz" \\
                      | tar xz --strip-components=1 -C app
                    echo "    FenixAgent: $(ls app/ | wc -l) files/dirs in app/"

                    echo ">>> Downloading aos-auto-test (feat/jenkins-pipeline)..."
                    curl -SL "https://gh-proxy.com/https://api.github.com/repos/youtaking/aos-auto-test/tarball/feat/jenkins-pipeline" \\
                      | tar xz --strip-components=1 -C autotest
                    echo "    aos-auto-test: $(ls autotest/ | wc -l) files/dirs in autotest/"

                    echo ""
                    echo "<<< [1/7] Clone Repos — DONE"
                '''.replace('__PR_BRANCH__', params.PR_BRANCH)
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

        stage('Build Unit Runner') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[2b] Build Unit Runner — START"
                    echo "============================================================"
                    docker build -t unit-runner:latest -f autotest/Dockerfile.unit-runner .
                    echo ""
                    echo "<<< [2b] Build Unit Runner — DONE"
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
" > test_targets.txt 2>&1

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
    command: 'pytest __TEST_TARGETS__ -v --tb=short --base-url=http://rcs:3001 --json-report --json-report-file=/app/results/report.json'

  unit-runner:
    image: unit-runner:latest
    volumes:
      - __WORKSPACE__/autotest/unit_tests:/app/tests
      - __WORKSPACE__/app/src:/app/tests/app/src:ro
    working_dir: /app/tests
    command: 'sh -c "mkdir -p results && bun test --reporter=junit --reporter-outfile=results/unit-junit.xml"'
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
                    echo ">>> Starting unit-runner (bun:test)..."
                '''
                sh "docker-compose -p ${PROJECT_NAME} up unit-runner"
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
                    echo ">>> Starting test-runner (streaming logs)..."
                '''
                sh "docker-compose -p ${PROJECT_NAME} logs -f test-runner &"
                sh "docker-compose -p ${PROJECT_NAME} up test-runner"
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
                    echo ">>> Copying unit-junit.xml from unit-runner container..."
                    docker cp __PROJECT_NAME__-unit-runner-1:/app/tests/results/unit-junit.xml unit-junit.xml || true

                    echo ">>> Copying report.json from test-runner container..."
                    docker cp __PROJECT_NAME__-test-runner-1:/app/results/report.json report.json || true
                '''.replace('__PROJECT_NAME__', PROJECT_NAME)

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

                        if [ -f unit-junit.xml ] && [ -n "$PIPELINE_ID" ]; then
                            echo ">>> Uploading unit test results..."
                            python3 -c "
import xml.etree.ElementTree as ET, json, sys
tree = ET.parse('unit-junit.xml')
results = []
for ts in tree.findall('.//testsuite'):
    for tc in ts.findall('testcase'):
        r = {'name': tc.get('name'), 'status': 'passed', 'duration_ms': int(float(tc.get('time', 0)) * 1000)}
        if tc.find('failure') is not None:
            r['status'] = 'failed'
            r['failure_message'] = tc.find('failure').get('message', '')
        if tc.find('skipped') is not None:
            r['status'] = 'skipped'
        results.append(r)
print(json.dumps(results))
" > unit-results.json 2>/dev/null
                            if [ -f unit-results.json ]; then
                                JUNIT_XML=$(python3 -c "import sys; print(open('unit-junit.xml').read())" 2>/dev/null)
                                curl -s -X POST __AUTOTEST_URL__/api/unit-tests/results \\
                                  -H "Authorization: Bearer $TOKEN" \\
                                  -H "Content-Type: application/json" \\
                                  -d "{\"pipeline_id\": $PIPELINE_ID, \"junit_xml\": $(python3 -c "import json,sys; print(json.dumps(open('unit-junit.xml').read()))" 2>/dev/null)}"
                                echo ""
                                echo "    Unit test results uploaded."
                            fi
                        else
                            [ ! -f unit-junit.xml ] && echo "    WARNING: unit-junit.xml not found."
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
                echo ">>> Removing images..."
                docker rmi -f __IMAGE_TAG__ || true
                docker rmi -f __MIGRATE_IMAGE_TAG__ || true
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
