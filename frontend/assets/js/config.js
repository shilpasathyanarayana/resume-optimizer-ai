// config.js — load this FIRST, without defer
// config.js
const API_BASE = (
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1'
)
  ? 'http://localhost:8000'
  : 'https://resume-optimizer-ai-2.onrender.com';
  
const FREE_LIMIT = 5;