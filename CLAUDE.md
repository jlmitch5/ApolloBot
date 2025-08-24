# ApolloBot - Claude Code Project Context

## About This Project
ApolloBot is a UAD Console automation tool for Universal Audio Apollo 8 interfaces. It automates monitor switching between main (analog) and alt (S/PDIF) outputs for custom monitoring setups.

## 📖 Project Documentation
**The README.md file is the primary source of truth for this project.** It contains:
- Complete project overview and hardware setup details
- Implementation methodology and TCP protocol messages
- Installation instructions and usage examples  
- Technical specifications and requirements
- Credit to open source dependencies

## 🤖 For Claude Code Users
When working on this project:
1. **Always read README.md first** to understand the complete context
2. The main executable is `apollobot.py` - a self-contained Python script
3. Uses only Python standard library (no external dependencies)
4. Communicates with UAD Console via TCP on port 4710
5. Key functionality: monitor switching, background daemon, status monitoring

## 🎯 Quick Context
- **Problem**: Manual workflow to switch between analog monitors and S/PDIF-connected tube amp
- **Solution**: TCP protocol automation that syncs with hardware Alt button
- **Result**: One-command monitor switching with background sync daemon

See README.md for full details and usage instructions.