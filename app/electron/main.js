const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {
  const mainWindow = new BrowserWindow({
   width: 1200,
    height: 800,

    center: true,
    resizable: true,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, '..', 'preload', 'preload.js')
    }
  });

  // Load the blank HTML entry file
  mainWindow.loadFile(path.join(__dirname, '..', 'renderer', 'index.html'));
  // Allow mouse clicks to pass through the window
  mainWindow.setIgnoreMouseEvents(true, {
      forward: true
  });
  mainWindow.setAlwaysOnTop(true, 'screen-saver');
  }

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
