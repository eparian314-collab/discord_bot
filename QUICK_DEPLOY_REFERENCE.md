# 🚀 EC2 Automated Deployment - Quick Reference

## Setup (One Time Only)

### 1. Add EC2 Host to .env
```bash
echo "EC2_HOST=ec2-12-34-56-78.us-east-1.compute.amazonaws.com" >> .env
```

### 2. Verify SSH Key Location
Your SSH key should be at: `C:\Users\YourName\.ssh\hippobot-ec2.pem`

**That's it! You're ready to deploy.**

---

## 🎯 Main Commands

### Deploy to EC2 (Automated Everything)
```powershell
.\deploy_to_ec2.ps1
```
**What it does:**
- ✅ Commits your changes
- ✅ Pushes to GitHub  
- ✅ SSHs into EC2
- ✅ Pulls latest code
- ✅ Installs dependencies
- ✅ Restarts bot
- ✅ Verifies it's running

### Check Bot Status
```powershell
.\check_ec2_status.ps1
```
**Shows you:**
- Is the bot running?
- Current branch and commit
- Memory/CPU usage
- Last 10 log entries

### View Live Logs
```powershell
.\view_ec2_logs.ps1
```
**Live tail of bot logs** - Press Ctrl+C to exit

---

## 🔧 Advanced Options

### Fast Deploy (Skip Tests)
```powershell
.\deploy_to_ec2.ps1 -SkipTests
```

### Custom Commit Message
```powershell
.\deploy_to_ec2.ps1 -Message "Fixed translation bug #42"
```

### Deploy to Different Branch
```powershell
.\deploy_to_ec2.ps1 -Branch "main"
```

### Specify EC2 Host Manually
```powershell
.\deploy_to_ec2.ps1 -EC2Host "ec2-12-34-56-78.compute.amazonaws.com"
```

### Use Different SSH Key
```powershell
.\deploy_to_ec2.ps1 -KeyPath "C:\path\to\other-key.pem"
```

---

## 📊 Typical Workflow

### Daily Development
```powershell
# 1. Make changes to code
# 2. Test locally
python -m discord_bot.scripts.simulation_test

# 3. Deploy to EC2
.\deploy_to_ec2.ps1 -Message "Updated translation system"

# 4. Check logs
.\view_ec2_logs.ps1
```

### Quick Check
```powershell
# Is my bot running?
.\check_ec2_status.ps1
```

### Emergency Stop
```powershell
ssh -i ~/.ssh/hippobot-ec2.pem ubuntu@your-host 'pkill -f python.*main.py'
```

---

## 🐛 Troubleshooting

### Bot Won't Start
```powershell
# View full logs
.\view_ec2_logs.ps1 -Lines 200

# Or SSH and check manually
ssh -i ~/.ssh/hippobot-ec2.pem ubuntu@your-host
cd ~/discord_bot
tail -100 logs/bot.log
```

### "SSH Key Not Found"
```powershell
# Check if key exists
Test-Path "~\.ssh\hippobot-ec2.pem"

# If not, download from AWS and save as:
# C:\Users\YourName\.ssh\hippobot-ec2.pem
```

### "Permission Denied"
```powershell
# Fix key permissions (Windows):
# 1. Right-click hippobot-ec2.pem > Properties > Security
# 2. Remove all users except yourself
# 3. Give yourself Full Control
```

### "Can't Connect to EC2"
```powershell
# Test connection manually
ssh -i ~/.ssh/hippobot-ec2.pem ubuntu@your-host

# Check EC2 security group allows SSH (port 22) from your IP
```

---

## 🎓 How It Works

### Local Side (Your PC)
1. **deploy_to_ec2.ps1** runs preflight checks
2. Commits any changes
3. Pushes to GitHub
4. Connects to EC2 via SSH

### Remote Side (EC2)
1. Stops running bot
2. Pulls latest code from GitHub
3. Updates Python dependencies
4. Starts bot in background
5. Returns PID and status

### Result
✅ Your bot is updated and running on EC2 - **no manual steps required!**

---

## 📚 Full Documentation

For complete details, see: **EC2_DEPLOYMENT_GUIDE.md**

---

## 🔐 Security Best Practices

✅ Never commit `.pem` files to git  
✅ Keep `.env` in `.gitignore`  
✅ Use restrictive permissions on SSH keys  
✅ Rotate keys periodically  
✅ Use AWS IAM roles when possible  

---

## 💡 Pro Tips

### Add Alias for Quick Deploy
```powershell
# Add to your PowerShell profile:
function deploy { .\deploy_to_ec2.ps1 @args }

# Then just:
deploy -Message "Quick fix"
```

### Git Commit Before Deploy
```powershell
git add -A
git commit -m "Your changes"
.\deploy_to_ec2.ps1
```

### View Logs While Deploying
```powershell
# Terminal 1: Deploy
.\deploy_to_ec2.ps1

# Terminal 2: Watch logs
.\view_ec2_logs.ps1
```

---

## 🆘 Need Help?

1. Check **EC2_DEPLOYMENT_GUIDE.md** for detailed troubleshooting
2. Review bot logs: `.\view_ec2_logs.ps1`
3. Test locally first: `python -m discord_bot.scripts.simulation_test`
4. Verify EC2 is accessible: `.\check_ec2_status.ps1`

---

**Happy Deploying! 🦛🚀**
