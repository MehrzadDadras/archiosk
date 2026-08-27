import * as THREE from './vendor/three/three.module.js';
import { OrbitControls } from './vendor/three/OrbitControls.js';

const COLORS = { lobby: 0x2f80ed, mechanical: 0xf2994a, electrical: 0x27ae60, default: 0x8e9aa7 };
const MAX_SPACES = 500;
const MAX_WALLS = 1000;
const MAX_VERTICES = 10000;

function colorFor(name = '') {
  const key = name.toLowerCase();
  return COLORS[Object.keys(COLORS).find(k => k !== 'default' && key.includes(k))] || COLORS.default;
}

function pointsOf(space) {
  return (space.boundary_polygon_2d || []).map(p => Array.isArray(p) ? p : [p.x, p.y]);
}

function labelSprite(text, color = '#e8eef7') {
  const canvas = document.createElement('canvas');
  canvas.width = 512; canvas.height = 96;
  const ctx = canvas.getContext('2d');
  ctx.font = 'bold 28px sans-serif'; ctx.fillStyle = color; ctx.textAlign = 'center';
  ctx.fillText(text, 256, 56);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), transparent: true, depthTest: false }));
  sprite.scale.set(5, 0.95, 1);
  return sprite;
}

export class SpatialViewport {
  constructor(container, options = {}) {
    this.container = typeof container === 'string' ? document.querySelector(container) : container;
    if (!this.container) throw new Error('SpatialViewport requires a valid container');
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(options.background ?? 0x101820);
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100000);
    this.camera.position.set(260, 220, 300);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.container.appendChild(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true; this.controls.dampingFactor = 0.08;
    this.controls.target.set(0, 40, 0);
    this.root = new THREE.Group(); this.scene.add(this.root);
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x263238, 1.8));
    this.scene.add(new THREE.DirectionalLight(0xffffff, 1.4));
    this._resize = () => this.resize();
    window.addEventListener('resize', this._resize);
    this.resize();
    this._animate = () => { this.controls.update(); this.renderer.render(this.scene, this.camera); this._raf = requestAnimationFrame(this._animate); };
    this._animate();
  }

  resize() {
    const width = this.container.clientWidth || 640, height = this.container.clientHeight || 480;
    this.camera.aspect = width / height; this.camera.updateProjectionMatrix(); this.renderer.setSize(width, height, false);
  }

  setData(data) {
    if (!data || typeof data !== 'object') throw new TypeError('Spatial viewport data must be an object');
    if (!Array.isArray(data.storeys) && !Array.isArray(data.levels)) throw new TypeError('Spatial viewport data requires storeys');
    if (!Array.isArray(data.spaces) || data.spaces.length > MAX_SPACES) throw new RangeError(`spaces exceed maximum of ${MAX_SPACES}`);
    if (!Array.isArray(data.walls) || data.walls.length > MAX_WALLS) throw new RangeError(`walls exceed maximum of ${MAX_WALLS}`);
    const vertexCount = (data.spaces || []).reduce((n, s) => n + (s.boundary_polygon_2d || []).length, 0);
    if (vertexCount > MAX_VERTICES) throw new RangeError(`vertices exceed maximum of ${MAX_VERTICES}`);
    this.root.clear();
    const levels = data.storeys || data.levels || [];
    const scale = 1 / (data.coordinate_scale || 1);
    levels.forEach(level => {
      const y = Number(level.elevation_feet ?? level.elevation ?? 0) * scale;
      const grid = new THREE.GridHelper(500 * scale, 25, 0x526273, 0x2a3744);
      grid.position.y = y; this.root.add(grid);
      const label = labelSprite(level.name); label.position.set(-245 * scale, y + 1, -245 * scale); label.scale.multiplyScalar(Math.max(scale, 0.25)); this.root.add(label);
    });
    (data.spaces || []).forEach(space => this._addSpace(space, levels, scale));
    (data.walls || []).forEach(wall => this._addWall(wall, scale));
    return this;
  }

  _addSpace(space, levels, scale) {
    const pts = pointsOf(space); if (pts.length < 3) return;
    const level = levels.find(l => l.name === space.level); const base = Number(level?.elevation_feet ?? level?.elevation ?? 0) * scale;
    const shape = new THREE.Shape(); shape.moveTo(pts[0][0] * scale, -pts[0][1] * scale);
    pts.slice(1).forEach(p => shape.lineTo(p[0] * scale, -p[1] * scale)); shape.closePath();
    const height = Number(space.height) * scale;
    const mesh = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: height, bevelEnabled: false }), new THREE.MeshStandardMaterial({ color: colorFor(space.name), transparent: true, opacity: 0.28, side: THREE.DoubleSide }));
    mesh.rotation.x = -Math.PI / 2; mesh.position.y = base; mesh.userData = { type: 'space', id: space.id, name: space.name }; this.root.add(mesh);
    const center = pts.reduce((a, p) => [a[0] + p[0], a[1] + p[1]], [0, 0]).map(v => v / pts.length);
    const label = labelSprite(space.name); label.position.set(center[0] * scale, base + height + 2 * scale, -center[1] * scale); label.scale.multiplyScalar(Math.max(scale, 0.25)); this.root.add(label);
  }

  _addWall(wall, scale) {
    const [a, b] = wall.baseline || []; if (!a || !b) return;
    const p0 = Array.isArray(a) ? a : [a.x, a.y], p1 = Array.isArray(b) ? b : [b.x, b.y];
    const length = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]), angle = Math.atan2(p1[1] - p0[1], p1[0] - p0[0]);
    const thickness = Number(wall.thickness) * scale, height = Number(wall.height) * scale;
    const openings = (wall.openings || []).map(o => ({ start: Number(o.offset) * scale, end: (Number(o.offset) + Number(o.width)) * scale, height: Number(o.height) * scale }));
    const spans = []; let cursor = 0;
    openings.sort((x, y) => x.start - y.start).forEach(o => { if (o.start > cursor) spans.push([cursor, o.start, height]); cursor = Math.max(cursor, o.end); });
    if (cursor < length * scale) spans.push([cursor, length * scale, height]);
    spans.forEach(([start, end, h]) => {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(end - start, h, thickness), new THREE.MeshStandardMaterial({ color: 0x737b83, roughness: 0.9 }));
      mesh.position.set((p0[0] * scale + Math.cos(angle) * (start + end) / 2), h / 2, -(p0[1] * scale + Math.sin(angle) * (start + end) / 2)); mesh.rotation.y = -angle; mesh.userData = { type: 'wall', id: wall.id }; this.root.add(mesh);
    });
    openings.forEach(o => { if (o.height < height) { const lintel = new THREE.Mesh(new THREE.BoxGeometry(o.end - o.start, height - o.height, thickness), new THREE.MeshStandardMaterial({ color: 0x737b83 })); lintel.position.set(p0[0] * scale + Math.cos(angle) * (o.start + o.end) / 2, o.height + (height - o.height) / 2, -(p0[1] * scale + Math.sin(angle) * (o.start + o.end) / 2)); lintel.rotation.y = -angle; this.root.add(lintel); } });
  }

  dispose() { cancelAnimationFrame(this._raf); window.removeEventListener('resize', this._resize); this.controls.dispose(); this.renderer.dispose(); this.container.removeChild(this.renderer.domElement); }
}

export default SpatialViewport;
