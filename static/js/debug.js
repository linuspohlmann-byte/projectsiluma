// Debug utility - disable console logs in production
// Set window.DEBUG = true in console to enable debug logs
const DEBUG_ENABLED = window.DEBUG === true || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

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

