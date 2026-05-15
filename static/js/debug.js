// Debug utility - disable console logs in production
// Set window.DEBUG = true in console to enable debug logs
// Quiet by default — set window.DEBUG = true in the console for verbose logs
const DEBUG_ENABLED = window.DEBUG === true;

// Override console methods in production
if (!DEBUG_ENABLED) {
  const noop = () => {};
  const originalLog = console.log;
  const originalDebug = console.debug;
  
  // Keep console.error and console.warn for actual errors
  console.log = noop;
  console.debug = noop;
  
  // Optionally restore for specific debug calls
  window.debugLog = originalLog;
  window.debugDebug = originalDebug;
} else {
  window.debugLog = console.log;
  window.debugDebug = console.debug;
}

export const DEBUG = DEBUG_ENABLED;
export const log = DEBUG_ENABLED ? console.log.bind(console) : () => {};
export const debug = DEBUG_ENABLED ? console.debug.bind(console) : () => {};
export const warn = console.warn.bind(console);
export const error = console.error.bind(console);

