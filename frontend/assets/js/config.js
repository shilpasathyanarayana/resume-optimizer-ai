// config.js — load this FIRST, without defer
const API_BASE = (
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1'
)
  ? 'http://localhost:8000/api'
  : '/api';

const FREE_LIMIT = 5;