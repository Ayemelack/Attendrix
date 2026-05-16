/* Attendrix Network Topology Visualizer
 *
 * Interactive campus network topology renderer.
 * Demonstrates networking concepts:
 *   - Star topology layout (broker-core at center, building nodes radiating)
 *   - Real-time latency visualization on edges
 *   - Packet loss indicators (dashed vs solid lines)
 *   - Animated data flow (moving particles along active connections)
 *   - Node status color-coding (healthy/degraded/offline)
 *   - Interactive hover tooltips with node details
 *   - Responsive canvas resizing
 */

(function (global) {
  'use strict';

  var Topology = {
    canvas: null,
    ctx: null,
    nodes: [],
    connections: [],
    animFrame: null,
    tooltipEl: null,
    hoveredNode: null,
    mouseX: 0,
    mouseY: 0,
    particles: [],
    animationTime: 0,
  };

  var COLORS = {
    healthy: '#10B981',
    degraded: '#F59E0B',
    offline: '#EF4444',
    broker: '#4F46E5',
    brokerGlow: 'rgba(79,70,229,0.3)',
    lineHealthy: 'rgba(16,185,129,0.25)',
    lineDegraded: 'rgba(245,158,11,0.25)',
    lineOffline: 'rgba(239,68,68,0.15)',
    label: 'rgba(255,255,255,0.5)',
    bgGrad: 'rgba(79,70,229,0.04)',
  };

  /* ── INIT ── */

  function init(canvasId) {
    Topology.canvas = document.getElementById(canvasId || 'topologyCanvas');
    if (!Topology.canvas) return false;
    Topology.ctx = Topology.canvas.getContext('2d');

    Topology.tooltipEl = document.createElement('div');
    Topology.tooltipEl.style.cssText = [
      'position: fixed; display: none; pointer-events: none; z-index: 9999;',
      'background: rgba(15,23,42,0.95); border: 1px solid rgba(255,255,255,0.08);',
      'border-radius: 8px; padding: 0.5rem 0.7rem;',
      'font-family: Inter, sans-serif; font-size: 0.65rem;',
      'color: #fff; backdrop-filter: blur(12px);',
      'box-shadow: 0 8px 32px rgba(0,0,0,0.4);',
      'max-width: 200px; line-height: 1.5;',
    ].join(' ');
    document.body.appendChild(Topology.tooltipEl);

    Topology.canvas.addEventListener('mousemove', onMouseMove);
    Topology.canvas.addEventListener('mouseleave', function () {
      Topology.hoveredNode = null;
      Topology.tooltipEl.style.display = 'none';
      Topology.canvas.style.cursor = 'default';
    });

    /* Responsive resize */
    var resizeTimer;
    window.addEventListener('resize', function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        var rect = Topology.canvas.parentElement.getBoundingClientRect();
        Topology.canvas.width = rect.width || 500;
        Topology.canvas.height = 280;
      }, 150);
    });

    return true;
  }

  /* ── LAYOUT ── */

  function layout(nodes, broker) {
    Topology.nodes = [];
    Topology.particles = [];

    var canvas = Topology.canvas;
    var W = canvas.width, H = canvas.height;
    var cx = W / 2, cy = H / 2;

    var buildings = nodes.filter(function (n) { return n.type !== 'broker'; });
    var brokerNode = nodes.filter(function (n) { return n.type === 'broker'; })[0] || null;
    var count = buildings.length;
    var radius = Math.min(W, H) * 0.32;

    /* Center broker */
    var centerNode = {
      x: cx, y: cy, r: 16,
      name: brokerNode ? brokerNode.name : 'Core Broker',
      status: brokerNode ? brokerNode.status : 'healthy',
      latency: brokerNode ? brokerNode.latency_ms : 0,
      packetLoss: 0,
      isBroker: true,
    };
    Topology.nodes.push(centerNode);

    /* Building nodes around circle */
    buildings.forEach(function (n, i) {
      var angle = (i / count) * 2 * Math.PI - Math.PI / 2;
      Topology.nodes.push({
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
        r: 12,
        name: n.name,
        status: n.status || 'healthy',
        latency: n.latency_ms || 0,
        packetLoss: n.packet_loss || 0,
        isBroker: false,
        lastSeen: n.last_seen || '—',
      });
    });

    /* Build connections (broker to each building) */
    Topology.connections = [];
    for (var i = 1; i < Topology.nodes.length; i++) {
      Topology.connections.push({
        from: 0,
        to: i,
      });
    }

    /* Generate data particles along each connection */
    Topology.connections.forEach(function (conn) {
      for (var p = 0; p < 2; p++) {
        Topology.particles.push({
          connIdx: Topology.connections.indexOf(conn),
          progress: Math.random(),
          speed: 0.002 + Math.random() * 0.004,
          size: 1.5 + Math.random() * 1.5,
          offset: p,
        });
      }
    });

    updateLegend(nodes);
  }

  /* ── LEGEND ── */

  function updateLegend(nodes) {
    var legendEl = document.getElementById('topologyLegend');
    if (!legendEl) return;
    var healthy = nodes.filter(function (n) { return n.status === 'healthy'; }).length;
    var degraded = nodes.filter(function (n) { return n.status === 'degraded'; }).length;
    var offline = nodes.filter(function (n) { return n.status === 'offline'; }).length;
    legendEl.innerHTML =
      '<span><span class="dot" style="background:' + COLORS.healthy + ';"></span> Healthy: ' + healthy + '</span>' +
      '<span><span class="dot" style="background:' + COLORS.degraded + ';"></span> Degraded: ' + degraded + '</span>' +
      '<span><span class="dot" style="background:' + COLORS.offline + ';"></span> Offline: ' + offline + '</span>';
  }

  /* ── DRAW ── */

  function draw() {
    var ctx = Topology.ctx;
    if (!ctx) return;
    var W = ctx.canvas.width, H = ctx.canvas.height;

    ctx.clearRect(0, 0, W, H);

    /* Background gradient */
    var grad = ctx.createRadialGradient(W / 2, H / 2, 10, W / 2, H / 2, W * 0.5);
    grad.addColorStop(0, COLORS.bgGrad);
    grad.addColorStop(1, 'rgba(10,15,30,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);

    if (Topology.nodes.length < 2) {
      ctx.fillStyle = COLORS.label;
      ctx.font = '12px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No network nodes to display', W / 2, H / 2);
      return;
    }

    var broker = Topology.nodes[0];
    if (!broker) return;

    /* ── Draw connection lines ── */
    Topology.connections.forEach(function (conn) {
      var from = Topology.nodes[conn.from];
      var to = Topology.nodes[conn.to];
      if (!from || !to) return;

      var isOnline = to.status === 'healthy';
      var isDegraded = to.status === 'degraded';
      var pktLoss = to.packetLoss || 0;

      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);

      if (pktLoss > 5) {
        /* High packet loss — dotted line */
        ctx.setLineDash([2, 4]);
        ctx.strokeStyle = COLORS.lineOffline;
      } else if (isDegraded) {
        ctx.setLineDash([4, 3]);
        ctx.strokeStyle = COLORS.lineDegraded;
      } else {
        ctx.setLineDash([]);
        ctx.strokeStyle = COLORS.lineHealthy;
      }

      ctx.lineWidth = isOnline ? 1.5 : 1;
      ctx.stroke();
      ctx.setLineDash([]);

      /* Latency label at midpoint */
      var mx = (from.x + to.x) / 2;
      var my = (from.y + to.y) / 2;
      ctx.fillStyle = COLORS.label;
      ctx.font = '7px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(to.latency + 'ms' + (pktLoss > 0 ? ' | ' + pktLoss.toFixed(1) + '% loss' : ''), mx, my - 5);

      /* Packet loss warning icon */
      if (pktLoss > 10) {
        ctx.fillStyle = COLORS.offline;
        ctx.font = '8px sans-serif';
        ctx.fillText('!', mx, my + 8);
      }
    });

    /* ── Animated data particles ── */
    if (navigator.onLine !== false) {
      Topology.particles.forEach(function (p) {
        var conn = Topology.connections[p.connIdx];
        if (!conn) return;
        var from = Topology.nodes[conn.from];
        var to = Topology.nodes[conn.to];
        if (!from || !to || to.status !== 'healthy') return;

        p.progress += p.speed;
        if (p.progress > 1) p.progress = 0;

        var x = from.x + (to.x - from.x) * p.progress;
        var y = from.y + (to.y - from.y) * p.progress;

        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);

        var alpha = Math.sin(p.progress * Math.PI) * 0.6 + 0.2;
        ctx.fillStyle = 'rgba(79,70,229,' + alpha + ')';
        ctx.fill();
      });
    }

    /* ── Draw nodes ── */
    Topology.nodes.forEach(function (node) {
      var color = node.status === 'healthy' ? COLORS.healthy
        : node.status === 'degraded' ? COLORS.degraded
        : COLORS.offline;

      /* Glow effect */
      var glowGrad = ctx.createRadialGradient(node.x, node.y, 2, node.x, node.y, node.r * 2.5);
      glowGrad.addColorStop(0, color + '33');
      glowGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = glowGrad;
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.r * 2.5, 0, Math.PI * 2);
      ctx.fill();

      /* Node circle */
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
      ctx.fillStyle = node.isBroker ? COLORS.brokerGlow : 'rgba(255,255,255,0.04)';
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = node.isBroker ? 2.5 : 1.5;
      ctx.stroke();

      /* Status indicator inside node */
      if (node.status === 'healthy') {
        ctx.beginPath();
        ctx.arc(node.x, node.y, 3, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      } else if (node.status === 'offline') {
        ctx.beginPath();
        ctx.moveTo(node.x - 4, node.y - 4);
        ctx.lineTo(node.x + 4, node.y + 4);
        ctx.moveTo(node.x + 4, node.y - 4);
        ctx.lineTo(node.x - 4, node.y + 4);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      /* Label */
      ctx.fillStyle = node.isBroker ? 'rgba(255,255,255,0.8)' : COLORS.label;
      ctx.font = node.isBroker ? 'bold 8px Inter, sans-serif' : '7px Inter, sans-serif';
      ctx.textAlign = 'center';
      var labelY = node.y + node.r + (node.isBroker ? 18 : 14);
      ctx.fillText(node.name, node.x, labelY);

      /* Broker badge */
      if (node.isBroker) {
        ctx.fillStyle = 'rgba(79,70,229,0.12)';
        ctx.fillRect(node.x - 20, node.y - 20, 40, 40);
        ctx.fillStyle = 'rgba(255,255,255,0.1)';
        ctx.font = '6px Inter, sans-serif';
        ctx.fillText('BROKER', node.x, node.y + 3);
      }
    });

    /* ── Hover tooltip ── */
    if (Topology.hoveredNode) {
      var n = Topology.hoveredNode;
      var statusLabel = n.status === 'healthy' ? 'Healthy'
        : n.status === 'degraded' ? 'Degraded' : 'Offline';
      var html = '<strong>' + n.name + '</strong><br>' +
        'Status: ' + statusLabel + '<br>' +
        'Latency: ' + n.latency + 'ms' +
        (n.packetLoss !== undefined ? '<br>Packet Loss: ' + n.packetLoss.toFixed(1) + '%' : '') +
        (n.lastSeen && n.lastSeen !== '—' ? '<br>Last Seen: ' + n.lastSeen : '');
      Topology.tooltipEl.innerHTML = html;
    }
  }

  /* ── ANIMATION LOOP ── */

  function animate() {
    draw();
    Topology.animFrame = requestAnimationFrame(animate);
  }

  /* ── START ANIMATION ── */

  function start(nodes, broker, canvasId) {
    if (Topology.animFrame) {
      cancelAnimationFrame(Topology.animFrame);
      Topology.animFrame = null;
    }
    if (!Topology.canvas && !init(canvasId)) return;
    layout(nodes, broker);
    animate();
  }

  /* ── STOP ── */

  function stop() {
    if (Topology.animFrame) {
      cancelAnimationFrame(Topology.animFrame);
      Topology.animFrame = null;
    }
    if (Topology.tooltipEl) {
      Topology.tooltipEl.style.display = 'none';
    }
  }

  /* ── UPDATE (re-layout with new data) ── */

  function update(nodes, broker) {
    var wasRunning = Topology.animFrame !== null;
    if (wasRunning) stop();
    layout(nodes, broker);
    if (wasRunning) animate();
  }

  /* ── MOUSE HANDLER ── */

  function onMouseMove(e) {
    var rect = Topology.canvas.getBoundingClientRect();
    var scaleX = Topology.canvas.width / rect.width;
    var scaleY = Topology.canvas.height / rect.height;
    var mx = (e.clientX - rect.left) * scaleX;
    var my = (e.clientY - rect.top) * scaleY;

    Topology.hoveredNode = null;
    for (var i = Topology.nodes.length - 1; i >= 0; i--) {
      var n = Topology.nodes[i];
      var dx = mx - n.x;
      var dy = my - n.y;
      var dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < n.r + 8) {
        Topology.hoveredNode = n;
        break;
      }
    }

    if (Topology.hoveredNode) {
      Topology.canvas.style.cursor = 'pointer';
      Topology.tooltipEl.style.display = 'block';
      Topology.tooltipEl.style.left = (e.clientX + 12) + 'px';
      Topology.tooltipEl.style.top = (e.clientY - 10) + 'px';
    } else {
      Topology.canvas.style.cursor = 'default';
      Topology.tooltipEl.style.display = 'none';
    }
  }

  /* ── EXPOSE ── */

  global.AttendrixTopology = {
    init: init,
    start: start,
    stop: stop,
    update: update,
    layout: layout,
    draw: draw,
  };

})(window);
