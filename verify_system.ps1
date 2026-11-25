Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   ContextIQ System Health Verification   " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Port checks
Write-Host "`n[1] Checking Active Network Ports..." -ForegroundColor Yellow
$ports = Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 3001, 8000, 8001, 5433 } | Select-Object LocalPort, OwningProcess | Sort-Object LocalPort -Unique
$ports | Format-Table -AutoSize

$activePortList = $ports.LocalPort
foreach ($p in @(3001, 8000, 8001, 5433)) {
    if ($activePortList -contains $p) {
        Write-Host "  [OK] Port $p is actively listening." -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Port $p is NOT listening." -ForegroundColor Red
    }
}

# 2. Core Backend API Health
Write-Host "`n[2] Checking Core Backend API (:8000)..." -ForegroundColor Yellow
try {
    $res = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -Method Get
    Write-Host "  [OK] /api/v1/health returned: $($res | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] Failed to reach /api/v1/health: $_" -ForegroundColor Red
}

# 3. Data Engine API Health
Write-Host "`n[3] Checking Data Engine API (:8001)..." -ForegroundColor Yellow
try {
    $res = Invoke-WebRequest -Uri "http://localhost:8001/docs" -UseBasicParsing
    Write-Host "  [OK] Data Engine Docs returned HTTP $($res.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] Failed to reach Data Engine: $_" -ForegroundColor Red
}

function Invoke-EndpointCheck {
    param(
        [string]$Uri
    )
    try {
        $req = [System.Net.WebRequest]::Create($Uri)
        $req.Timeout = 2000
        $req.Method = "GET"
        $resp = $req.GetResponse()
        $status = [int]$resp.StatusCode
        $resp.Close()
        return $status
    } catch [System.Net.WebException] {
        if ($_.Response) {
            $status = [int]$_.Response.StatusCode
            $_.Response.Close()
            return $status
        }
        return $null
    } catch {
        return $null
    }
}

# 4. Phase 4 Adaptive Intelligence API Endpoints (:8000)
Write-Host "`n[4] Checking Adaptive Intelligence API Endpoints (:8000)..." -ForegroundColor Yellow
$adaptiveEndpoints = @(
    "/api/v1/adaptive/profile",
    "/api/v1/adaptive/focus-windows",
    "/api/v1/adaptive/task-ranking",
    "/api/v1/adaptive/interventions/active",
    "/api/v1/adaptive/bandit/policy",
    "/api/v1/adaptive/effectiveness/overview",
    "/api/v1/adaptive/notifications"
)
foreach ($ep in $adaptiveEndpoints) {
    if (-not ($activePortList -contains 8000)) {
        Write-Host "  [SKIP] $ep (Port 8000 offline)" -ForegroundColor DarkGray
        continue
    }
    $status = Invoke-EndpointCheck -Uri ("http://localhost:8000" + $ep)
    if ($status -in @(200, 401)) {
        Write-Host "  [OK] $ep -> HTTP $status" -ForegroundColor Green
    } elseif ($status) {
        Write-Host "  [WARN] $ep -> HTTP $status" -ForegroundColor Yellow
    } else {
        Write-Host "  [FAIL] $ep -> Connection Failed" -ForegroundColor Red
    }
}

# 5. Phase 5 External Ecosystem API Endpoints (:8000)
Write-Host "`n[5] Checking External Ecosystem & Cross-Platform Endpoints (:8000)..." -ForegroundColor Yellow
$ecosystemEndpoints = @(
    "/api/v1/integrations",
    "/api/v1/integrations/google/auth-url",
    "/api/v1/integrations/microsoft/auth-url",
    "/api/v1/scheduling/proposals/generate",
    "/api/v1/devices",
    "/api/v1/activity/timeline",
    "/api/v1/context/locations"
)
foreach ($ep in $ecosystemEndpoints) {
    if (-not ($activePortList -contains 8000)) {
        Write-Host "  [SKIP] $ep (Port 8000 offline)" -ForegroundColor DarkGray
        continue
    }
    $status = Invoke-EndpointCheck -Uri ("http://localhost:8000" + $ep)
    if ($status -in @(200, 401, 405)) {
        Write-Host "  [OK] $ep -> HTTP $status" -ForegroundColor Green
    } elseif ($status) {
        Write-Host "  [WARN] $ep -> HTTP $status" -ForegroundColor Yellow
    } else {
        Write-Host "  [FAIL] $ep -> Connection Failed" -ForegroundColor Red
    }
}

# 6. Phase 6 Advanced Predictive Intelligence & Decision Support Endpoints (:8000)
Write-Host "`n[6] Checking Phase 6 Predictive Intelligence & Decision Support Endpoints (:8000)..." -ForegroundColor Yellow
$phase6Endpoints = @(
    "/api/v1/analytics/recovery/benchmark",
    "/api/v1/causal/questions",
    "/api/v1/counterfactual/candidates",
    "/api/v1/sequence/benchmark",
    "/api/v1/survival/benchmark",
    "/api/v1/uncertainty/audit",
    "/api/v1/simulation/scenarios",
    "/api/v1/analytics/simulation/scenarios"
)
foreach ($ep in $phase6Endpoints) {
    if (-not ($activePortList -contains 8000)) {
        Write-Host "  [SKIP] $ep (Port 8000 offline)" -ForegroundColor DarkGray
        continue
    }
    $status = Invoke-EndpointCheck -Uri ("http://localhost:8000" + $ep)
    if ($status -in @(200, 401)) {
        Write-Host "  [OK] $ep -> HTTP $status" -ForegroundColor Green
    } elseif ($status) {
        Write-Host "  [WARN] $ep -> HTTP $status" -ForegroundColor Yellow
    } else {
        Write-Host "  [FAIL] $ep -> Connection Failed" -ForegroundColor Red
    }
}

# 7. Frontend Dashboard Pages
Write-Host "`n[7] Checking Frontend Dashboard Pages (:3001 / :3000)..." -ForegroundColor Yellow
$fePort = 3001
$routes = @(
    @{ Path = "/"; Label = "Dashboard Overview" },
    @{ Path = "/context"; Label = "Context & Micro-Delays" },
    @{ Path = "/predictions"; Label = "Forgetting Risk Predictions" },
    @{ Path = "/insights"; Label = "Behavioral Insights" },
    @{ Path = "/recommendations"; Label = "Contextual Recommendations" },
    @{ Path = "/tasks"; Label = "Tasks & Interruption Logger" },
    @{ Path = "/adaptive/profile"; Label = "Digital Twin Profile" },
    @{ Path = "/adaptive/focus"; Label = "Focus Windows Explorer" },
    @{ Path = "/adaptive/interventions"; Label = "Intervention Center" },
    @{ Path = "/adaptive/learning"; Label = "Contextual Bandit Learning" },
    @{ Path = "/adaptive/effectiveness"; Label = "Causal Effectiveness" },
    @{ Path = "/adaptive/notifications"; Label = "Notification Controls" },
    @{ Path = "/settings/integrations"; Label = "Integration Management" },
    @{ Path = "/calendar"; Label = "Smart Calendar & Scheduling" },
    @{ Path = "/activity"; Label = "Cross-Device Timeline" },
    @{ Path = "/context/locations"; Label = "Location Intelligence" }
)

foreach ($r in $routes) {
    if (-not ($activePortList -contains $fePort)) {
        Write-Host "  [SKIP] $($r.Label) ($($r.Path)) (Port $fePort offline)" -ForegroundColor DarkGray
        continue
    }
    $status = Invoke-EndpointCheck -Uri ("http://localhost:$fePort" + $r.Path)
    if ($status -eq 200) {
        Write-Host "  [OK] $($r.Label) ($($r.Path)) -> HTTP 200 OK" -ForegroundColor Green
    } elseif ($status) {
        Write-Host "  [WARN] $($r.Label) ($($r.Path)) -> HTTP $status" -ForegroundColor Yellow
    } else {
        Write-Host "  [FAIL] $($r.Label) ($($r.Path)) -> Connection Failed" -ForegroundColor Red
    }
}

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "       Verification Audit Completed       " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
