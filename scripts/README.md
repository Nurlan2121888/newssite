# Automatic news updates

Windows Task Scheduler runs `manage.py fetch_news` daily at **09:00, 15:00 and 21:00 Baku time**. Codex, VS Code and a terminal do not need to be open.

The computer must be awake, connected to the internet and signed in to the Windows account that installed the task. Missed executions are handled by Windows when the task becomes available. Overlapping scheduled runs are prevented.

Install or update the task from the project directory:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_news_schedule.ps1
```

Run once immediately:

```powershell
Start-ScheduledTask -TaskName 'Gundem-News-Fetch'
```

Check the schedule and last execution:

```powershell
Get-ScheduledTask -TaskName 'Gundem-News-Fetch'
Get-ScheduledTaskInfo -TaskName 'Gundem-News-Fetch'
```

Execution output is appended to `logs/fetch_news.log`. The existing bot continues to collect only current-month news and preserve publication statuses.

To remove the schedule:

```powershell
Unregister-ScheduledTask -TaskName 'Gundem-News-Fetch' -Confirm:$false
```
