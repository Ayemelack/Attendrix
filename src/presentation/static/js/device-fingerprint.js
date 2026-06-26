/* Attendrix Device Fingerprint & Geolocation Client
 *
 * Collects client-side signals for anti-proxy security:
 *   1. Device fingerprint (screen, timezone, canvas, fonts, WebGL)
 *   2. Geolocation (with user consent)
 *   3. Network information (connection type, latency)
 *   4. Battery status (if available)
 *
 * This data is sent alongside attendance markers and login requests
 * to verify the user's physical presence and device consistency.
 */

(function (global) {
  'use strict';

  var AttendrixSecurity = {
    fingerprint: null,
    geoPosition: null,
    networkInfo: null,
    batteryInfo: null,
  };

  /* ── DEVICE FINGERPRINT ── */

  function generateFingerprint() {
    var components = [];

    /* Screen */
    components.push('scr:' + screen.width + 'x' + screen.height);
    components.push('cd:' + screen.colorDepth);
    components.push('pixel:' + (window.devicePixelRatio || 1));

    /* Timezone */
    try {
      var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      components.push('tz:' + (tz || 'unknown'));
    } catch (e) {
      components.push('tz:unknown');
    }
    components.push('tzoff:' + new Date().getTimezoneOffset());

    /* Language */
    components.push('lang:' + (navigator.language || ''));
    components.push('langs:' + (navigator.languages || []).join(','));

    /* Platform */
    components.push('plt:' + (navigator.platform || ''));
    components.push('mem:' + (navigator.deviceMemory || ''));
    components.push('cores:' + (navigator.hardwareConcurrency || ''));

    /* Touch support */
    components.push('touch:' + ('ontouchstart' in window));

    /* Canvas fingerprint */
    try {
      var canvas = document.createElement('canvas');
      canvas.width = 200;
      canvas.height = 50;
      var ctx = canvas.getContext('2d');
      ctx.textBaseline = 'alphabetic';
      ctx.fillStyle = '#f60';
      ctx.fillRect(0, 0, 100, 50);
      ctx.fillStyle = '#069';
      ctx.font = '14px Arial';
      ctx.fillText('Attendrix', 5, 30);
      ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
      ctx.font = '12px sans-serif';
      ctx.fillText('Crypto', 110, 20);
      ctx.fillStyle = '#ccc';
      ctx.font = '10px monospace';
      ctx.fillText(navigator.userAgent, 10, 45);
      components.push('canvas:' + hashString(canvas.toDataURL()));
    } catch (e) {
      components.push('canvas:error');
    }

    /* WebGL fingerprint */
    try {
      var glCanvas = document.createElement('canvas');
      var gl = glCanvas.getContext('webgl') || glCanvas.getContext('experimental-webgl');
      if (gl) {
        var debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
        if (debugInfo) {
          components.push('gl_vendor:' + hashString(gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) || ''));
          components.push('gl_renderer:' + hashString(gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) || ''));
        }
      }
    } catch (e) {
      components.push('gl:error');
    }

    /* User agent (hashed) */
    components.push('ua:' + hashString(navigator.userAgent));

    return hashString(components.join('|||'));
  }

  /* ── SIMPLE HASH FUNCTION ── */

  function hashString(str) {
    var hash = 0;
    for (var i = 0; i < str.length; i++) {
      var char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return Math.abs(hash).toString(16).padStart(8, '0');
  }

  /* ── GEOLOCATION ── */

  function getGeolocation() {
    return new Promise(function (resolve) {
      if (!navigator.geolocation) {
        resolve(null);
        return;
      }
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          resolve({
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
            accuracy: pos.coords.accuracy,
            timestamp: new Date(pos.timestamp).toISOString(),
          });
        },
        function () {
          resolve(null);
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 300000,
        }
      );
    });
  }

  /* ── NETWORK INFORMATION ── */

  function getNetworkInfo() {
    var info = {};
    var conn = navigator.connection ||
               navigator.mozConnection ||
               navigator.webkitConnection;
    if (conn) {
      info.effectiveType = conn.effectiveType;  /* slow-2g, 2g, 3g, 4g */
      info.downlink = conn.downlink;            /* Mbps */
      info.rtt = conn.rtt;                      /* ms */
      info.saveData = conn.saveData || false;   /* data saver */
    } else {
      info.effectiveType = 'unknown';
      info.downlink = 0;
      info.rtt = 0;
    }
    info.online = navigator.onLine;
    return info;
  }

  /* ── BATTERY STATUS ── */

  function getBatteryInfo() {
    return new Promise(function (resolve) {
      if (!navigator.getBattery) {
        resolve(null);
        return;
      }
      navigator.getBattery().then(function (battery) {
        resolve({
          level: battery.level,
          charging: battery.charging,
          chargingTime: battery.chargingTime,
          dischargingTime: battery.dischargingTime,
        });
      }).catch(function () {
        resolve(null);
      });
    });
  }

  /* ── COMBINE ALL SIGNALS ── */

  function collectAllSignals() {
    AttendrixSecurity.fingerprint = generateFingerprint();
    AttendrixSecurity.networkInfo = getNetworkInfo();

    return Promise.all([
      getGeolocation().then(function (pos) {
        AttendrixSecurity.geoPosition = pos;
      }),
      getBatteryInfo().then(function (bat) {
        AttendrixSecurity.batteryInfo = bat;
      }),
    ]).then(function () {
      return {
        fingerprint: AttendrixSecurity.fingerprint,
        geolocation: AttendrixSecurity.geoPosition,
        network: AttendrixSecurity.networkInfo,
        battery: AttendrixSecurity.batteryInfo,
        collected_at: new Date().toISOString(),
      };
    });
  }

  /* ── ATTACH TO LOGIN FORM ── */

  function attachToLoginForm(formSelector) {
    var form = document.querySelector(formSelector || 'form');
    if (!form) return;

    form.addEventListener('submit', function (e) {
      collectAllSignals().then(function (signals) {
        /* Add hidden fields */
        var fpInput = document.createElement('input');
        fpInput.type = 'hidden';
        fpInput.name = 'device_fingerprint';
        fpInput.value = signals.fingerprint;
        form.appendChild(fpInput);

        if (signals.geolocation) {
          var latInput = document.createElement('input');
          latInput.type = 'hidden';
          latInput.name = 'geo_lat';
          latInput.value = signals.geolocation.lat;
          form.appendChild(latInput);

          var lngInput = document.createElement('input');
          lngInput.type = 'hidden';
          lngInput.name = 'geo_lng';
          lngInput.value = signals.geolocation.lng;
          form.appendChild(lngInput);
        }
      });
    });
  }

  /* ── API FETCH WRAPPER (for SPAs) ── */

  function fetchWithSignals(url, options) {
    options = options || {};
    return collectAllSignals().then(function (signals) {
      options.headers = options.headers || {};
      options.headers['X-Device-Fingerprint'] = signals.fingerprint;
      if (signals.geolocation) {
        options.headers['X-Geo-Lat'] = signals.geolocation.lat;
        options.headers['X-Geo-Lng'] = signals.geolocation.lng;
      }
      options.headers['X-Network-Type'] = signals.network.effectiveType;
      options.headers['X-Network-RTT'] = signals.network.rtt;
      return fetch(url, options);
    });
  }

  /* ── EXPOSE ── */

  global.AttendrixSecurity = {
    generateFingerprint: generateFingerprint,
    getGeolocation: getGeolocation,
    getNetworkInfo: getNetworkInfo,
    collectAllSignals: collectAllSignals,
    attachToLoginForm: attachToLoginForm,
    fetchWithSignals: fetchWithSignals,
    getFingerprint: function () { return AttendrixSecurity.fingerprint; },
    getGeoPosition: function () { return AttendrixSecurity.geoPosition; },
    getNetwork: function () { return AttendrixSecurity.networkInfo; },
  };

  /* Auto-collect on page load (non-blocking) */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      collectAllSignals().catch(function () {});
    });
  } else {
    collectAllSignals().catch(function () {});
  }

})(window);
