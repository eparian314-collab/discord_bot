# 🚀 Automated EC2 Deployment Setup

## Quick Start

### 1. One-Time Setup

Add your EC2 host to `.env`:
```bash
EC2_HOST=ec2-12-34-56-78.us-east-1.compute.amazonaws.com
```

Make sure your SSH key exists at:
```
C:\Users\YourName\.ssh\hippobot-ec2.pem
```

### 2. Deploy with One Command

```powershell
.\deploy_to_ec2.ps1
```

That's it! The script will:
- ✅ Commit your changes
- ✅ Push to GitHub
- ✅ SSH into EC2
- ✅ Pull latest code
- ✅ Install dependencies
- ✅ Restart the bot

### 3. Advanced Usage

```powershell
# Deploy with custom commit message
.\deploy_to_ec2.ps1 -Message "Fixed translation bug"

# Skip local tests (faster)
.\deploy_to_ec2.ps1 -SkipTests

# Deploy to specific host
.\deploy_to_ec2.ps1 -EC2Host "ec2-12-34-56-78.compute.amazonaws.com"

# Deploy to different branch
.\deploy_to_ec2.ps1 -Branch "main"

# Use different SSH key
.\deploy_to_ec2.ps1 -KeyPath "C:\path\to\your\key.pem"
```

## What It Does

### Local Steps:
1. Verifies git repository
2. Finds EC2 host from .env (or prompts you)
3. Checks SSH key exists
4. Commits any uncommitted changes
5. Runs local simulation tests
6. Pushes to GitHub

### Remote Steps (via SSH):
1. Stops running bot instance
2. Navigates to project directory
3. Pulls latest code from GitHub
4. Activates Python virtual environment
5. Installs/updates dependencies
6. Runs database migrations
7. Starts bot in background
8. Verifies bot is running

## Monitoring After Deployment

The script will show you helpful commands:

```powershell
# View live logs
ssh -i ~/.ssh/hippobot-ec2.pem ubuntu@your-ec2-host 'tail -f ~/discord_bot/logs/bot.log'

# Check if bot is running
ssh -i ~/.ssh/hippobot-ec2.pem ubuntu@your-ec2-host 'ps aux | grep python.*main.py'

# Stop the bot
ssh -i ~/.ssh/hippobot-ec2.pem ubuntu@your-ec2-host 'pkill -f python.*main.py'
```

## Troubleshooting

### "SSH key not found"
Make sure your `.pem` file is in the right location:
```powershell
# Check if key exists
Test-Path "~\.ssh\hippobot-ec2.pem"

# If not, specify custom path
.\deploy_to_ec2.ps1 -KeyPath "C:\path\to\your\key.pem"
```

### "Permission denied (publickey)"
Your SSH key permissions might be wrong:
```powershell
# On Windows, right-click the .pem file > Properties > Security
# Make sure only your user has access
```

### "Bot failed to start"
The script will show the last 20 lines of logs. To see more:
```powershell
ssh -i ~/.ssh/hippobot-ec2.pem ubuntu@your-ec2-host 'tail -50 ~/discord_bot/logs/bot.log'
```

### "Can't find EC2_HOST"
Add it to your `.env` file:
```bash
echo "EC2_HOST=your-ec2-hostname.compute.amazonaws.com" >> .env
```

## Setting Up Scheduled Deployments (Optional)

You can automate deployments even further with Windows Task Scheduler:

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., daily at 3 AM)
4. Action: Start a program
   - Program: `powershell.exe`
   - Arguments: `-File "C:\path\to\discord_bot\deploy_to_ec2.ps1" -SkipTests`
   - Start in: `C:\path\to\discord_bot`

## Security Notes

- ✅ Never commit your `.pem` SSH key to git
- ✅ Keep `.env` in `.gitignore`
- ✅ Use read-only permissions on your SSH key
- ✅ Consider using AWS Systems Manager Session Manager for even more security

## Integration with GitHub Actions (Future)

You can also trigger EC2 deployment automatically on push to main:

```yaml
# .github/workflows/deploy.yml
name: Deploy to EC2
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to EC2
        run: |
          # SSH and pull code
```

But for now, the PowerShell script gives you full control!
