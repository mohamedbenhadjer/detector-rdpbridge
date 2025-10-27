/**
 * Node.js Playwright CDP Injector
 * 
 * Patches chromium.launch() to force:
 * - --remote-debugging-port=0 (ephemeral port)
 * - headless: false
 * 
 * Discovers CDP WebSocket URL and writes metadata to ~/.pw_watchdog/cdp/<runId>.json
 * 
 * Usage: NODE_OPTIONS="--require /path/to/pw_injector.js" npx playwright test
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const WATCHDOG_DIR = process.env.PW_WATCHDOG_DIR || path.join(os.homedir(), '.pw_watchdog');
const CDP_DIR = path.join(WATCHDOG_DIR, 'cdp');

// Ensure CDP directory exists
if (!fs.existsSync(CDP_DIR)) {
  fs.mkdirSync(CDP_DIR, { recursive: true });
}

/**
 * Generate or retrieve runId
 */
function getRunId() {
  if (process.env.PW_WATCHDOG_RUN_ID) {
    return process.env.PW_WATCHDOG_RUN_ID;
  }
  
  // Generate from pid and timestamp
  const startMs = Date.now();
  return `${process.pid}-${startMs}`;
}

/**
 * Parse DevToolsActivePort file to get CDP WebSocket URL
 */
function readDevToolsActivePort(userDataDir, maxRetries = 20, delayMs = 500) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    
    const tryRead = () => {
      attempts++;
      const activePortPath = path.join(userDataDir, 'DevToolsActivePort');
      
      if (fs.existsSync(activePortPath)) {
        try {
          const content = fs.readFileSync(activePortPath, 'utf-8').trim();
          const lines = content.split('\n');
          
          if (lines.length >= 2) {
            const port = parseInt(lines[0], 10);
            const wsEndpoint = lines[1];
            
            resolve({
              port,
              wsUrl: `ws://127.0.0.1:${port}${wsEndpoint}`,
              devtoolsActivePortPath: activePortPath
            });
            return;
          }
        } catch (err) {
          // File might be in the process of being written
        }
      }
      
      if (attempts < maxRetries) {
        setTimeout(tryRead, delayMs);
      } else {
        reject(new Error('DevToolsActivePort not found after retries'));
      }
    };
    
    tryRead();
  });
}

/**
 * Write CDP metadata to watchdog directory
 */
function writeCdpMetadata(runId, cdpInfo) {
  const metadataPath = path.join(CDP_DIR, `${runId}.json`);
  const metadata = {
    runId,
    ...cdpInfo,
    timestamp: new Date().toISOString()
  };
  
  try {
    fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));
    console.log(`[pw_injector] CDP metadata written: ${metadataPath}`);
  } catch (err) {
    console.error(`[pw_injector] Failed to write CDP metadata: ${err.message}`);
  }
}

/**
 * Patch Playwright's chromium.launch()
 */
function patchPlaywright() {
  const runId = getRunId();
  console.log(`[pw_injector] Injector loaded, runId: ${runId}`);
  
  // Hook into module loading to intercept Playwright
  const Module = require('module');
  const originalRequire = Module.prototype.require;
  
  Module.prototype.require = function (id) {
    const module = originalRequire.apply(this, arguments);
    
    // Detect Playwright module
    if (id === 'playwright' || id === '@playwright/test' || id.endsWith('/playwright')) {
      try {
        if (module.chromium && module.chromium.launch) {
          const originalLaunch = module.chromium.launch;
          
          module.chromium.launch = async function (options = {}) {
            console.log('[pw_injector] Patching chromium.launch()');
            
            // Force headless: false
            options.headless = false;
            
            // Add remote debugging port
            options.args = options.args || [];
            if (!options.args.some(arg => arg.startsWith('--remote-debugging-port'))) {
              options.args.push('--remote-debugging-port=0');
            }
            
            console.log('[pw_injector] Launching Chromium with CDP enabled');
            const browser = await originalLaunch.call(this, options);
            
            // Extract user data dir from browser context
            try {
              const context = browser._initializer || browser;
              const userDataDir = context.userDataDir || context._userDataDir;
              
              if (userDataDir) {
                // Read CDP info asynchronously
                readDevToolsActivePort(userDataDir)
                  .then(cdpInfo => {
                    writeCdpMetadata(runId, cdpInfo);
                  })
                  .catch(err => {
                    console.error(`[pw_injector] Failed to read CDP info: ${err.message}`);
                  });
              } else {
                console.warn('[pw_injector] Could not determine user data directory');
              }
            } catch (err) {
              console.error(`[pw_injector] Error extracting CDP info: ${err.message}`);
            }
            
            return browser;
          };
          
          // Also patch launchPersistentContext
          if (module.chromium.launchPersistentContext) {
            const originalLaunchPersistent = module.chromium.launchPersistentContext;
            
            module.chromium.launchPersistentContext = async function (userDataDir, options = {}) {
              console.log('[pw_injector] Patching chromium.launchPersistentContext()');
              
              options.headless = false;
              options.args = options.args || [];
              if (!options.args.some(arg => arg.startsWith('--remote-debugging-port'))) {
                options.args.push('--remote-debugging-port=0');
              }
              
              const context = await originalLaunchPersistent.call(this, userDataDir, options);
              
              // Read CDP info
              readDevToolsActivePort(userDataDir)
                .then(cdpInfo => {
                  writeCdpMetadata(runId, cdpInfo);
                })
                .catch(err => {
                  console.error(`[pw_injector] Failed to read CDP info: ${err.message}`);
                });
              
              return context;
            };
          }
        }
      } catch (err) {
        console.error(`[pw_injector] Failed to patch Playwright: ${err.message}`);
      }
    }
    
    return module;
  };
}

// Apply patches
patchPlaywright();


