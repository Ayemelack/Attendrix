/* Attendrix Network Connectivity Monitor
 *
 * Client-side network awareness layer:
 *   1. Monitors online/offline transitions
 *   2. Measures server latency via periodic pings
 *   3. Detects connection quality changes
 *   4. Triggers UI indicators on the dashboard
 *   5. Queues POST requests when offline via Service Worker
 */

(function (global) {
  'use strict';

  var NetworkMonitor = {
    isOnline: navigator.onLine,
    latency: 0,
    connectionType: 'unknown',
    lastPing: null,
    pingInterval: null,
    listeners: [],
    history: [],
    maxHistory: 50,
  };

  /* ── PING SERVER FOR LATENCY ── */

  function pingServer() {
    var start = performance.now();
    return fetch('/api/ping', {
      method: 'GET',
      cache: 'no-store',
    }).then(function (resp) {
      if (resp.ok) {
        var elapsed = Math.round(performance.now() - start);
        NetworkMonitor.latency = elapsed;
        NetworkMonitor.lastPing = new Date().toISOString();
        NetworkMonitor.history.push({
          latency: elapsed,
          time: NetworkMonitor.lastPing,
          online: true,
        });
        if (NetworkMonitor.history.length > NetworkMonitor.maxHistory) {
          NetworkMonitor.history.shift();
        }
        notifyListeners({ type: 'pong', latency: elapsed });
        return elapsed;
      }
      throw new Error('Ping failed');
    }).catch(function () {
      NetworkMonitor.latency = -1;
      var entry = {
        latency: -1,
        time: new Date().toISOString(),
        online: false,
      };
      NetworkMonitor.history.push(entry);
      if (NetworkMonitor.history.length > NetworkMonitor.maxHistory) {
        NetworkMonitor.history.shift();
      }
      notifyListeners({ type: 'pong', latency: -1, error: 'server_unreachable' });
      return -1;
    });
  }

  /* ── CONNECTION TYPE DETECTION ── */

  function detectConnectionType() {
    var conn = navigator.connection ||
               navigator.mozConnection ||
               navigator.webkitConnection;
    if (conn) {
      var type = conn.effectiveType || 'unknown';
      var downlink = conn.downlink || 0;
      NetworkMonitor.connectionType = type;
      return { type: type, downlink: downlink, rtt: conn.rtt };
    }
    NetworkMonitor.connectionType = navigator.onLine ? 'ethernet' : 'offline';
    return { type: NetworkMonitor.connectionType, downlink: 0, rtt: 0 };
  }

  /* ── LATENCY QUALITY LABEL ── */

  function getLatencyLabel() {
    var lat = NetworkMonitor.latency;
    if (lat < 0) return 'offline';
    if (lat < 50) return 'excellent';
    if (lat < 150) return 'good';
    if (lat < 300) return 'fair';
    if (lat < 500) return 'poor';
    return 'very_poor';
  }

  function getLatencyColor() {
    var lat = NetworkMonitor.latency;
    if (lat < 0) return '#EF4444';
    if (lat < 50) return '#10B981';
    if (lat < 150) return '#10B981';
    if (lat < 300) return '#F59E0B';
    if (lat < 500) return '#F59E0B';
    return '#EF4444';
  }

  /* ── LISTENER SYSTEM ── */

  function notifyListeners(event) {
    NetworkMonitor.listeners.forEach(function (fn) {
      try { fn(event); } catch (e) {}
    });
  }

  function addListener(fn) {
    if (typeof fn === 'function') {
      NetworkMonitor.listeners.push(fn);
    }
  }

  function removeListener(fn) {
    NetworkMonitor.listeners = NetworkMonitor.listeners.filter(function (f) {
      return f !== fn;
    });
  }

  /* ── GET FULL STATUS ── */

  function getStatus() {
    var conn = detectConnectionType();
    return {
      isOnline: NetworkMonitor.isOnline,
      latency: NetworkMonitor.latency,
      latencyLabel: getLatencyLabel(),
      latencyColor: getLatencyColor(),
      connectionType: conn.type,
      downlink: conn.downlink,
      rtt: conn.rtt,
      lastPing: NetworkMonitor.lastPing,
      historyCount: NetworkMonitor.history.length,
      onlineHistory: NetworkMonitor.history.filter(function (h) { return h.online; }).length,
      offlineHistory: NetworkMonitor.history.filter(function (h) { return !h.online; }).length,
    };
  }

  /* ── QUEUE OFFLINE REQUEST ── */

  function queueOfflineRequest(url, method, body) {
    if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({
        type: 'QUEUE_OFFLINE_OPERATION',
        payload: {
          url: url,
          method: method || 'POST',
          body: body || null,
        },
      });
    }
  }

  /* ── DASHBOARD UI INDICATOR ── */

  function createStatusIndicator(container) {
    var el = document.createElement('div');
    el.id = 'network-indicator';
    el.style.cssText = [
      'display: flex; align-items: center; gap: 0.4rem;',
      'font-size: 0.6rem; font-weight: 600; padding: 0.2rem 0.5rem;',
      'border-radius: 12px; white-space: nowrap; transition: all 0.3s;',
    ].join('');

    var dot = document.createElement('span');
    dot.style.cssText = 'width: 6px; height: 6px; border-radius: 50%; transition: background 0.3s;';
    el.appendChild(dot);

    var label = document.createElement('span');
    el.appendChild(label);

    if (container) container.appendChild(el);

    function update() {
      var status = getStatus();
      if (!status.isOnline) {
        el.style.background = 'rgba(239,68,68,0.08)';
        el.style.border = '1px solid rgba(239,68,68,0.12)';
        el.style.color = '#EF4444';
        dot.style.background = '#EF4444';
        label.textContent = 'Offline';
      } else if (status.latency < 0) {
        el.style.background = 'rgba(245,158,11,0.08)';
        el.style.border = '1px solid rgba(245,158,11,0.12)';
        el.style.color = '#F59E0B';
        dot.style.background = '#F59E0B';
        label.textContent = 'Connecting...';
      } else {
        el.style.background = status.latency < 150
          ? 'rgba(16,185,129,0.08)'
          : 'rgba(245,158,11,0.08)';
        el.style.border = '1px solid ' + (status.latency < 150
          ? 'rgba(16,185,129,0.12)'
          : 'rgba(245,158,11,0.12)');
        el.style.color = status.latency < 150 ? '#10B981' : '#F59E0B';
        dot.style.background = status.latency < 150 ? '#10B981' : '#F59E0B';
        label.textContent = status.latency + 'ms';
      }
    }

    update();
    addListener(update);
    return el;
  }

  /* ── INIT ── */

  function init(pingIntervalMs) {
    pingIntervalMs = pingIntervalMs || 15000;

    detectConnectionType();

    /* Listen for online/offline events */
    window.addEventListener('online', function () {
      NetworkMonitor.isOnline = true;
      notifyListeners({ type: 'online' });
      pingServer();
    });

    window.addEventListener('offline', function () {
      NetworkMonitor.isOnline = false;
      NetworkMonitor.latency = -1;
      notifyListeners({ type: 'offline' });
    });

    /* Listen for connection changes */
    var conn = navigator.connection ||
               navigator.mozConnection ||
               navigator.webkitConnection;
    if (conn) {
      conn.addEventListener('change', function () {
        detectConnectionType();
        notifyListeners({ type: 'connection_change', info: getStatus() });
      });
    }

    /* Start periodic pings */
    pingServer();
    NetworkMonitor.pingInterval = setInterval(pingServer, pingIntervalMs);
  }

  /* ── EXPOSE ── */

  global.AttendrixNetwork = {
    init: init,
    getStatus: getStatus,
    getLatencyLabel: getLatencyLabel,
    getLatencyColor: getLatencyColor,
    ping: pingServer,
    addListener: addListener,
    removeListener: removeListener,
    createStatusIndicator: createStatusIndicator,
    queueOfflineRequest: queueOfflineRequest,
  };

})(window);
