const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')
const { spawn } = require('child_process')

let mainWindow
let openManusProcess

// 禁用证书验证（仅开发环境）
app.commandLine.appendSwitch('ignore-certificate-errors')

app.on('ready', () => {
  mainWindow = new BrowserWindow({
    width: 300,
    height: 400,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false // 允许非安全连接
    }
  })

  mainWindow.loadFile('index.html')
  mainWindow.setMenu(null)
  
  startOpenManus()

  mainWindow.on('closed', () => {
    if (openManusProcess) {
      openManusProcess.kill()
    }
  })
})

function startOpenManus() {
  try {
    // 使用跨平台路径解析
    const serverPath = path.join(__dirname, 'websocket_server.py')
    console.log('Starting Python server at:', serverPath)

    // 检查文件是否存在
    const fs = require('fs')
    if (!fs.existsSync(serverPath)) {
      throw new Error(`File not found: ${serverPath}`)
    }

    openManusProcess = spawn('python', [serverPath], {
      cwd: __dirname  // 设置工作目录
    })

    openManusProcess.stdout.on('data', (data) => {
      console.log(`Python stdout: ${data}`)
    })

    openManusProcess.stderr.on('data', (data) => {
      console.error(`Python stderr: ${data}`)
    })

    openManusProcess.on('close', (code) => {
      console.log(`Python process exited with code ${code}`)
    })

    openManusProcess.on('error', (err) => {
      console.error('Failed to start Python:', err)
      mainWindow.webContents.send('server-error', err.message)
    })

  } catch (err) {
    console.error('Server startup error:', err)
    if (mainWindow) {
      mainWindow.webContents.send('server-error', err.message)
    }
  }
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})