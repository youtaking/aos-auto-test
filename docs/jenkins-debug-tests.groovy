pipeline {
    agent any

    parameters {
        string(name: 'IMAGE_BUILD_NUMBER', description: 'Use images from which build number?', defaultValue: '')
        string(name: 'TEST_TARGETS', description: 'Custom test paths (leave empty to auto-resolve)', defaultValue: '')
    }

    environment {
        AUTOTEST_URL  = "http://100.105.181.173:8000"
        PROJECT_NAME  = "pr-debug-${BUILD_NUMBER}"
        IMAGE_TAG        = "pr-env-${params.IMAGE_BUILD_NUMBER}:${params.IMAGE_BUILD_NUMBER}"
        MIGRATE_IMAGE_TAG = "pr-env-${params.IMAGE_BUILD_NUMBER}-migrate:${params.IMAGE_BUILD_NUMBER}"

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
                    echo "#   Debug Tests — Build #__BUILD_NUMBER__"
                    echo "#                                                          #"
                    echo "#   Using images from Build #__IMAGE_BUILD_NUMBER__"
                    echo "#   Image:    __IMAGE_TAG__"
                    echo "#   Migrate:  __MIGRATE_IMAGE_TAG__"
                    echo "#   RCS Port: __RCS_PORT__ (host)"
                    echo "#                                                          #"
                    echo "############################################################"

                    if [ -z "__IMAGE_BUILD_NUMBER__" ]; then
                        echo ""
                        echo "ERROR: IMAGE_BUILD_NUMBER is required!"
                        echo "Please specify which build's images to use."
                        exit 1
                    fi

                    echo ""
                    echo ">>> Checking dependencies..."
                    if command -v python3 >/dev/null 2>&1; then
                        echo "    python3: $(python3 --version)"
                    elif command -v python >/dev/null 2>&1; then
                        echo '#!/bin/sh' > /usr/local/bin/python3
                        echo 'exec python "$@"' >> /usr/local/bin/python3
                        chmod +x /usr/local/bin/python3
                        echo "    python3 alias created."
                    else
                        apt-get update -qq && apt-get install -y -qq python3 > /dev/null 2>&1
                        echo "    python3 installed: $(python3 --version)"
                    fi

                    if ! command -v docker-compose >/dev/null 2>&1; then
                        curl -sSL "https://github.com/docker/compose/releases/download/v2.29.2/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
                        chmod +x /usr/local/bin/docker-compose
                    fi
                    echo "    docker-compose: $(docker-compose --version)"

                    echo ">>> Checking images exist..."
                    if ! docker image inspect __IMAGE_TAG__ > /dev/null 2>&1; then
                        echo "    ERROR: Image __IMAGE_TAG__ not found!"
                        echo "    Available pr-env images:"
                        docker images | grep "pr-env" || echo "    (none)"
                        exit 1
                    fi
                    if ! docker image inspect __MIGRATE_IMAGE_TAG__ > /dev/null 2>&1; then
                        echo "    ERROR: Image __MIGRATE_IMAGE_TAG__ not found!"
                        exit 1
                    fi
                    echo "    Both images found."
                    echo ">>> Dependencies ready."
                '''.replace('__BUILD_NUMBER__', BUILD_NUMBER)
                  .replace('__IMAGE_BUILD_NUMBER__', params.IMAGE_BUILD_NUMBER ?: '')
                  .replace('__IMAGE_TAG__', IMAGE_TAG)
                  .replace('__MIGRATE_IMAGE_TAG__', MIGRATE_IMAGE_TAG)
                  .replace('__RCS_PORT__', RCS_PORT)
            }
        }

        stage('Clone Test Code') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[1/5] Clone Test Code — START"
                    echo "============================================================"
                    rm -rf autotest app
                    mkdir -p autotest app

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
                                    if [ -s "${output}" ]; then
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

                    echo ">>> Downloading aos-auto-test (feat/jenkins-pipeline)..."
                    download_repo \\
                      "https://github.com/youtaking/aos-auto-test/archive/refs/heads/feat/jenkins-pipeline.tar.gz" \\
                      /tmp/autotest.tar.gz
                    tar xzf /tmp/autotest.tar.gz --strip-components=1 -C autotest
                    rm -f /tmp/autotest.tar.gz
                    echo "    aos-auto-test: $(ls autotest/ | wc -l) files/dirs"

                    echo ">>> Downloading FenixAgent source (main branch, for unit tests)..."
                    download_repo \\
                      "https://github.com/youtaking/FenixAgent/archive/refs/heads/main.tar.gz" \\
                      /tmp/fenix.tar.gz
                    tar xzf /tmp/fenix.tar.gz --strip-components=1 -C app
                    rm -f /tmp/fenix.tar.gz
                    echo "    FenixAgent: $(ls app/ | wc -l) files/dirs"
                    echo ""
                    echo "<<< [1/5] Clone Test Code — DONE"
                '''
            }
        }

        stage('Check Runner Images') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[1b] Check Runner Images — START"
                    echo "============================================================"

                    if docker image inspect test-runner:latest > /dev/null 2>&1; then
                        echo ">>> test-runner:latest already exists, skipping build."
                    else
                        echo ">>> test-runner:latest not found, building..."
                        docker build -t test-runner:latest -f Dockerfile.runner autotest/
                        echo "    test-runner:latest built."
                    fi

                    if docker image inspect unit-runner:latest > /dev/null 2>&1; then
                        echo ">>> unit-runner:latest already exists, skipping build."
                    else
                        echo ">>> unit-runner:latest not found, building..."
                        docker build -t unit-runner:latest -f Dockerfile.unit-runner autotest/
                        echo "    unit-runner:latest built."
                    fi

                    echo ""
                    echo "<<< [1b] Check Runner Images — DONE"
                '''
            }
        }

        stage('Resolve Tests') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[2/5] Resolve Tests — START"
                    echo "============================================================"
                '''

                // 如果用户手动指定了 TEST_TARGETS，转换路径后写入
                script {
                    if (params.TEST_TARGETS?.trim()) {
                        def targets = params.TEST_TARGETS.trim()
                        // tests/xxx -> /app/tests/xxx
                        targets = targets.replaceAll(/(^|\s)tests\//, '$1/app/tests/')
                        echo ">>> Using custom test targets: ${targets}"
                        writeFile file: 'test_targets.txt', text: targets
                    }
                }

                // 否则走 API / cases.txt 兜底
                script {
                    if (!params.TEST_TARGETS?.trim()) {
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
                            '''.replace('__AUTOTEST_URL__', AUTOTEST_URL)
                        }
                    }
                }

                sh '''
                    set +x
                    echo "    Final targets: $(cat test_targets.txt)"
                    echo ""
                    echo "<<< [2/5] Resolve Tests — DONE"
                '''
            }
        }

        stage('Write Compose') {
            steps {
                sh '''
                    set +x
                    echo ""
                    echo "============================================================"
                    echo "[3/5] Write Compose — START"
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
    command: 'pytest __TEST_TARGETS__ -v --tb=short --base-url=http://rcs:3001 --json-report --json-report-file=/app/results/report.json'

  unit-runner:
    image: unit-runner:latest
    volumes:
      - __WORKSPACE__/autotest/unit_tests:/app/tests
      - __WORKSPACE__/app:/app/fenix-source-parent:ro
'''.replace('__PG_PORT__', PG_PORT)
  .replace('__LITE_PORT__', LITE_PORT)
  .replace('__IMAGE_TAG__', IMAGE_TAG)
  .replace('__MIGRATE_IMAGE_TAG__', MIGRATE_IMAGE_TAG)
  .replace('__RCS_PORT__', RCS_PORT)
  .replace('__WORKSPACE__', env.WORKSPACE.replace('/var/jenkins_home', '/opt/1panel/apps/jenkins/jenkins/data'))
  .replace('__TEST_TARGETS__', readFile('test_targets.txt').trim())

                sh '''
                    set +x
                    echo ">>> Compose ready:"
                    echo "    postgres  -> host port __PG_PORT__"
                    echo "    litellm   -> host port __LITE_PORT__"
                    echo "    rcs       -> host port __RCS_PORT__"
                    echo "    test targets: __TEST_TARGETS__"
                    echo ""
                    echo "<<< [3/5] Write Compose — DONE"
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
                    echo "[4/5] Deploy — START"
                    echo "  Project: __PROJECT_NAME__"
                    echo "============================================================"

                    mkdir -p pg-init
                    cat > pg-init/10-create-litellm.sh << 'INITEOF'
#!/bin/sh
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE litellm;
EOSQL
INITEOF
                    chmod +x pg-init/10-create-litellm.sh

                    echo ">>> Preparing seed data..."
                    if [ -f autotest/data.sql ]; then
                      grep -v "^[\\\\]restrict\b\|^[\\\\]unrestrict\b" autotest/data.sql > seed-data.sql
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
                    docker-compose -p __PROJECT_NAME__ exec -T postgres \
                      psql -U rcs -d rcs -v ON_ERROR_STOP=1 -f /seed-data.sql
                    echo "    Seed data imported."

                    echo ">>> Starting litellm + rcs..."
                    docker-compose -p __PROJECT_NAME__ up -d litellm rcs

                    echo ">>> Waiting for RCS health check (max 10min)..."
                    echo "    Health URL: http://100.105.114.178:__RCS_PORT__/health"
                    for i in $(seq 1 120); do
                        if curl -sf http://100.105.114.178:__RCS_PORT__/health > /dev/null 2>&1; then
                            echo "    RCS is healthy! (after ~$((i*5))s)"
                            echo ""
                            echo "<<< [4/5] Deploy — DONE"
                            exit 0
                        fi
                        if [ $((i % 10)) -eq 0 ]; then
                            echo "    --- Attempt $i/120 (~$((i*5))s) - RCS logs ---"
                            docker-compose -p __PROJECT_NAME__ logs --tail=10 rcs 2>&1 || true
                        fi
                        sleep 5
                    done
                    echo "    ERROR: RCS health check timeout!"
                    docker-compose -p __PROJECT_NAME__ logs --tail=30 rcs 2>&1 || true
                    exit 1
                '''.replace('__PROJECT_NAME__', PROJECT_NAME)
                  .replace('__RCS_PORT__', RCS_PORT)
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
                sh "docker-compose -p ${PROJECT_NAME} up unit-runner || true"
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
                    echo "[5/5] Run Tests — START"
                    echo "============================================================"
                    echo ">>> Diagnosing test-runner volume mounts..."
                    docker run --rm -v __WORKSPACE__/autotest/tests:/app/tests alpine ls -la /app/tests/ 2>&1 | head -20
                    echo "---"
                    docker run --rm -v __WORKSPACE__/autotest/tests:/app/tests alpine ls -la /app/tests/api_suites/ 2>&1 | head -20
                    echo "---"
                    echo ">>> Starting test-runner (streaming logs)..."
                '''.replace('__WORKSPACE__', env.WORKSPACE.replace('/var/jenkins_home', '/opt/1panel/apps/jenkins/jenkins/data'))
                sh "docker-compose -p ${PROJECT_NAME} logs -f test-runner &"
                sh "docker-compose -p ${PROJECT_NAME} up test-runner"
                sh '''
                    set +x
                    echo ""
                    echo "<<< [5/5] Run Tests — DONE"
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
                    echo ">>> Copying unit-junit.xml from volume..."
                    cp __WORKSPACE__/autotest/unit_tests/results/unit-junit.xml unit-junit.xml 2>/dev/null || true

                    if [ -f unit-junit.xml ]; then
                        echo ">>> Unit test summary:"
                        python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('unit-junit.xml')
total = passed = failed = skipped = 0
for ts in tree.findall('.//testsuite'):
    cases = ts.findall('testcase')
    if not cases:
        continue
    for tc in cases:
        total += 1
        if tc.find('failure') is not None:
            failed += 1
        elif tc.find('skipped') is not None:
            skipped += 1
        else:
            passed += 1
print(f'    Total:   {total}')
print(f'    Passed:  {passed}')
print(f'    Failed:  {failed}')
print(f'    Skipped: {skipped}')
" 2>/dev/null || echo "    Could not parse unit-junit.xml"
                    else
                        echo "    WARNING: unit-junit.xml not found."
                    fi

                    echo ""
                    echo ">>> Copying report.json from volume..."
                    cp __WORKSPACE__/autotest/tests/results/report.json report.json 2>/dev/null || true

                    if [ -f report.json ]; then
                        echo ">>> API/UI Test summary:"
                        python3 -c "
import json, sys
try:
    r = json.load(open('report.json'))
    s = r.get('summary', {})
    print('    Total:   ' + str(s.get('total', 0)))
    print('    Passed:  ' + str(s.get('passed', 0)))
    print('    Failed:  ' + str(s.get('failed', 0)))
    print('    Skipped: ' + str(s.get('skipped', 0)))
    print('    Errors:  ' + str(s.get('errors', 0)))
except Exception as e:
    print('    Could not parse report: ' + str(e))
"
                    else
                        echo "    WARNING: report.json not found."
                    fi
                    echo ""
                    echo "<<< Collect Results — DONE"
                '''.replace('__PROJECT_NAME__', PROJECT_NAME)
                  .replace('__WORKSPACE__', env.WORKSPACE.replace('/var/jenkins_home', '/opt/1panel/apps/jenkins/jenkins/data'))
            }
        }
    }

    post {
        always {
            echo ""
            echo "============================================================"
            echo "Cleanup — START"
            echo "============================================================"
            sh '''
                set +x
                echo ">>> Stopping and removing containers..."
                docker-compose -p __PROJECT_NAME__ down -v || true
                echo ">>> Images NOT deleted (kept for reuse)."
                echo ""
                echo "<<< Cleanup — DONE"
                echo ""
                echo "============================================================"
                echo "Debug run finished. Build #__BUILD_NUMBER__"
                echo "============================================================"
            '''.replace('__PROJECT_NAME__', PROJECT_NAME)
              .replace('__BUILD_NUMBER__', BUILD_NUMBER)
        }
    }
}
