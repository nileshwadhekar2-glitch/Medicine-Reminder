/* Shared transport and safe HTML formatting. */
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
}
function localDate() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
const nativeFetch = window.fetch.bind(window);
window.fetch = async function(url, options) {
  const response = await nativeFetch(url, options);
  if (!response.ok) {
    let body;
    try { body = await response.json(); } catch (_) {}
    if (response.status === 401 && !String(url).endsWith('/login')) {
      for (const key of ['token','user_id','username']) localStorage.removeItem(key);
      location.href = 'index.html';
    }
    const detail = body?.detail;
    throw new Error(Array.isArray(detail) ? detail.map(e => e.msg).join('; ') : detail || `Request failed (${response.status})`);
  }
  return response;
};

function shouldNotify(reminder) {
  const key = `notified:${localStorage.getItem('user_id')}:${reminder.id}:${localDate()}`;
  if (sessionStorage.getItem(key)) return false;
  sessionStorage.setItem(key, '1');
  return true;
}
