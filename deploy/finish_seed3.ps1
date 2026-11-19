# One-off job: finish the real-model seed 3 variance run once the free daily token allowance has
# reset (00:00 UTC), then regenerate the results table and charts. Writes everything to
# results\seed3_done.txt. It does not commit or push anything.
Set-Location "C:\Users\NAA\Documents\Projects\agentguard"
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$python = "C:\Program Files\Python311\python.exe"
$log = "results\seed3_done.txt"
"Started $((Get-Date).ToUniversalTime().ToString('u'))" | Out-File $log

# Start-Process with file redirection: a plain `*>>` redirect of a native command can make the
# scheduled task's console host exit early (the first scheduled run died this way).
function Run-Python([string[]]$arguments, [string]$stdin = $null) {
    $out = "$log.out"; $err = "$log.err"
    $params = @{ FilePath = $python; ArgumentList = $arguments; NoNewWindow = $true; Wait = $true
                 PassThru = $true; RedirectStandardOutput = $out; RedirectStandardError = $err }
    if ($stdin) { $in = "$log.in"; $stdin | Out-File $in; $params.RedirectStandardInput = $in }
    $proc = Start-Process @params
    Get-Content $out, $err -ErrorAction SilentlyContinue | Out-File $log -Append
    return $proc.ExitCode
}

$code = Run-Python @("-m", "agentguard.harness.runner", "--backend", "groq", "--split", "test",
    "--per-category", "3", "--no-benign", "--configs", "none,all", "--seed", "3",
    "--temperature", "0.7", "--out", "results/runs/groq_var_s3.jsonl")
"Runner exit code: $code (75 means the daily allowance was still used up)" | Out-File $log -Append

Run-Python @("-m", "agentguard.harness.report") | Out-Null

$summary = @'
import json
rows = [json.loads(l) for l in open("results/runs/groq_var_s3.jsonl", encoding="utf-8")]
print("--- Seed 3 summary ---")
for cfg in ("none", "all"):
    r = [x for x in rows if x["config"] == cfg]
    print(f"{cfg}: {sum(x['outcome'] for x in r)} of {len(r)} attacks succeeded")
print("Edit README.md, docs/WRITEUP.md and the portfolio blog post only if 'all five' is no longer 0%.")
'@
$summary | Out-File "$log.py"
Run-Python @("$log.py") | Out-Null

"Finished $((Get-Date).ToUniversalTime().ToString('u'))" | Out-File $log -Append
Remove-Item "$log.out", "$log.err", "$log.in", "$log.py" -ErrorAction SilentlyContinue
