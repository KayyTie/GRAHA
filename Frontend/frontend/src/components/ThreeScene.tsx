import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';

export const StarfieldBackground: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    let width = container.clientWidth;
    let height = container.clientHeight;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    // Camera distance setup: setting initial Z-axis distance from scene origin
    camera.position.z = 15;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    container.appendChild(renderer.domElement);

    // Background Starfield
    const starsGeometry = new THREE.BufferGeometry();
    const starsCount = 1500;
    const posArray = new Float32Array(starsCount * 3);
    const colorArray = new Float32Array(starsCount * 3);

    for (let i = 0; i < starsCount * 3; i += 3) {
      posArray[i] = (Math.random() - 0.5) * 60;
      posArray[i + 1] = (Math.random() - 0.5) * 60;
      posArray[i + 2] = (Math.random() - 0.5) * 60 - 10; // Push them slightly back

      const intensity = Math.random() * 0.8 + 0.2; // 0.2 to 1.0 intensity
      colorArray[i] = intensity;
      colorArray[i + 1] = intensity;
      colorArray[i + 2] = intensity;
    }

    starsGeometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
    starsGeometry.setAttribute('color', new THREE.BufferAttribute(colorArray, 3));

    const starsMaterial = new THREE.PointsMaterial({
      size: 0.05,
      vertexColors: true,
      transparent: true,
      opacity: 0.8,
    });

    const starMesh = new THREE.Points(starsGeometry, starsMaterial);
    scene.add(starMesh);

    let animationFrameId: number;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      starMesh.rotation.y += 0.0003;
      starMesh.rotation.x += 0.0001;
      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!containerRef.current) return;
      width = containerRef.current.clientWidth;
      height = containerRef.current.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
      container.removeChild(renderer.domElement);
      renderer.dispose();
      starsGeometry.dispose();
      starsMaterial.dispose();
    };
  }, []);

  return <div ref={containerRef} className="absolute inset-0 w-full h-full bg-transparent" />;
};

interface PlanetSystemProps {
  isTransitioning?: boolean;
}

export const PlanetSystem: React.FC<PlanetSystemProps> = ({ isTransitioning = false }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const transRef = useRef<{ active: boolean; startTime: number }>({ active: false, startTime: 0 });

  useEffect(() => {
    if (isTransitioning && !transRef.current.active) {
      transRef.current = { active: true, startTime: performance.now() };
    }
  }, [isTransitioning]);

  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    let width = container.clientWidth;
    let height = container.clientHeight;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(3, width / height, 0.1, 1000);
    // Initial 15 degrees clockwise camera tilt in radians
    const initialTilt = -15 * (Math.PI / 180);
    camera.rotation.z = initialTilt;
    // Camera distance setup: setting initial Z-axis distance from scene origin
    camera.position.z = 15;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    container.appendChild(renderer.domElement);

    // Star (Sun) - Central white glowing sphere
    const starGeometry = new THREE.SphereGeometry(1, 64, 64);
    const starMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const star = new THREE.Mesh(starGeometry, starMaterial);
    scene.add(star);

    // --- Inner Planet (Planet 1) ---
    const planetGeometry = new THREE.SphereGeometry(0.1, 64, 64);
    const orbitRadius = 6.0;

    // We use SubtractEquation with SrcAlpha blending to achieve an inversion effect
    const planetMaterial = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      blending: THREE.CustomBlending,
      blendEquation: THREE.SubtractEquation,
      blendSrc: THREE.SrcAlphaFactor,
      blendDst: THREE.OneFactor,
      transparent: true,
      opacity: 1.0
    });

    const planet = new THREE.Mesh(planetGeometry, planetMaterial);

    // Orbit 1 Tilt
    const orbitGroup = new THREE.Group();
    orbitGroup.rotation.z = -Math.PI * (30 / 180);
    orbitGroup.rotation.x = Math.PI * (3 / 180);
    scene.add(orbitGroup);
    orbitGroup.add(planet);

    // Dotted Orbit 1 Line
    const orbitPathGeometry = new THREE.BufferGeometry();
    const orbitPoints = [];
    for (let i = 0; i <= 64; i++) {
      const theta = (i / 64) * Math.PI * 2;
      orbitPoints.push(new THREE.Vector3(Math.cos(theta) * orbitRadius, 0, Math.sin(theta) * orbitRadius));
    }
    orbitPathGeometry.setFromPoints(orbitPoints);
    const orbitPathMaterial = new THREE.LineDashedMaterial({
      color: 0xFFFFFF,
      dashSize: 0.25,
      gapSize: 0.25,
      transparent: true,
      opacity: 1.0
    });
    const orbitPath = new THREE.Line(orbitPathGeometry, orbitPathMaterial);
    // Camera distance line computation for dashed orbit visualization
    orbitPath.computeLineDistances();
    orbitGroup.add(orbitPath);

    // --- Outer Planet (Planet 2) - Larger orbit & opposite Z tilt ---
    const planetGeometry2 = new THREE.SphereGeometry(0.15, 64, 64);
    const orbitRadius2 = 10;

    const planetMaterial2 = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      blending: THREE.CustomBlending,
      blendEquation: THREE.SubtractEquation,
      blendSrc: THREE.SrcAlphaFactor,
      blendDst: THREE.OneFactor,
      transparent: true,
      opacity: 1.0
    });

    const planet2 = new THREE.Mesh(planetGeometry2, planetMaterial2);

    // Orbit 2 Tilt (Opposite tilt along Z-axis)
    const orbitGroup2 = new THREE.Group();
    orbitGroup2.rotation.z = Math.PI * (30 / 180);
    orbitGroup2.rotation.x = -Math.PI * (2 / 180);
    scene.add(orbitGroup2);
    orbitGroup2.add(planet2);

    // --- Dynamic Thick Tapered Solid White Orbital Ribbon Trails ---
    const RIBBON_SEGMENTS = 180;

    const ribbonGeo1 = new THREE.BufferGeometry();
    const ribbonPos1 = new Float32Array(RIBBON_SEGMENTS * 2 * 3);
    const ribbonIndices1: number[] = [];
    for (let i = 0; i < RIBBON_SEGMENTS - 1; i++) {
      const a = i * 2;
      const b = i * 2 + 1;
      const c = (i + 1) * 2;
      const d = (i + 1) * 2 + 1;
      ribbonIndices1.push(a, b, c);
      ribbonIndices1.push(b, d, c);
    }
    ribbonGeo1.setAttribute('position', new THREE.BufferAttribute(ribbonPos1, 3));
    ribbonGeo1.setIndex(ribbonIndices1);

    const ribbonMat1 = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0,
    });
    const ribbonMesh1 = new THREE.Mesh(ribbonGeo1, ribbonMat1);
    orbitGroup.add(ribbonMesh1);

    const ribbonGeo2 = new THREE.BufferGeometry();
    const ribbonPos2 = new Float32Array(RIBBON_SEGMENTS * 2 * 3);
    const ribbonIndices2: number[] = [];
    for (let i = 0; i < RIBBON_SEGMENTS - 1; i++) {
      const a = i * 2;
      const b = i * 2 + 1;
      const c = (i + 1) * 2;
      const d = (i + 1) * 2 + 1;
      ribbonIndices2.push(a, b, c);
      ribbonIndices2.push(b, d, c);
    }
    ribbonGeo2.setAttribute('position', new THREE.BufferAttribute(ribbonPos2, 3));
    ribbonGeo2.setIndex(ribbonIndices2);

    const ribbonMat2 = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0,
    });
    const ribbonMesh2 = new THREE.Mesh(ribbonGeo2, ribbonMat2);
    orbitGroup2.add(ribbonMesh2);

    // Dotted Orbit 2 Line
    const orbitPathGeometry2 = new THREE.BufferGeometry();
    const orbitPoints2 = [];
    for (let i = 0; i <= 64; i++) {
      const theta = (i / 64) * Math.PI * 2;
      orbitPoints2.push(new THREE.Vector3(Math.cos(theta) * orbitRadius2, 0, Math.sin(theta) * orbitRadius2));
    }
    orbitPathGeometry2.setFromPoints(orbitPoints2);
    const orbitPathMaterial2 = new THREE.LineDashedMaterial({
      color: 0xFFFFFF,
      dashSize: 0.3,
      gapSize: 0.3,
      transparent: true,
      opacity: 0.85
    });
    const orbitPath2 = new THREE.Line(orbitPathGeometry2, orbitPathMaterial2);
    orbitPath2.computeLineDistances();
    orbitGroup2.add(orbitPath2);

    let angle1 = 0;
    const orbitSpeed1 = 0.02;

    let angle2 = Math.PI * 0.5;
    const orbitSpeed2 = 0.003;

    let scrollBoost = 0;
    let lastScrollY = window.scrollY;

    const handleScroll = () => {
      const currentScrollY = window.scrollY;
      const deltaY = Math.abs(currentScrollY - lastScrollY);
      lastScrollY = currentScrollY;
      scrollBoost += Math.min(0.06, deltaY * 0.0015);
      scrollBoost = Math.min(0.08, scrollBoost);
    };

    const handleWheel = (e: WheelEvent) => {
      const deltaY = Math.abs(e.deltaY);
      scrollBoost += Math.min(0.06, deltaY * 0.0012);
      scrollBoost = Math.min(0.08, scrollBoost);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('wheel', handleWheel, { passive: true });

    const fovStartTime = performance.now();
    const FOV_ANIMATION_DURATION = 2000; // 2 seconds startup reveal
    const TRANSITION_DURATION = 2500; // 2.5 seconds (0.5s slower) for scan zoom transition
    const targetY = -1.2; // Move system 10% lower on screen at the end of animation

    let animationFrameId: number;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      let speedMult = 1.0;

      if (transRef.current.active) {
        // Switch planet materials to pure solid white during transition
        if (planetMaterial.blending !== THREE.NormalBlending) {
          planetMaterial.blending = THREE.NormalBlending;
          planetMaterial.needsUpdate = true;
          planetMaterial2.blending = THREE.NormalBlending;
          planetMaterial2.needsUpdate = true;
        }

        const transElapsed = performance.now() - transRef.current.startTime;
        const transProgress = Math.min(1, transElapsed / TRANSITION_DURATION);
        const transEased = transProgress < 0.5
          ? 4 * transProgress * transProgress * transProgress
          : 1 - Math.pow(-2 * transProgress + 2, 3) / 2;

        // Speed ramps up dynamically up to 150x!
        speedMult = 1.0 + (150.0 - 1.0) * transEased;

        // Camera zooms back in over 2.5s: FOV 75 -> 3
        camera.fov = 75 - (75 - 3) * transEased;

        // Camera tilt reverses over 2.5s: 0 -> initialTilt (-15 deg)
        camera.rotation.z = initialTilt * transEased;

        // Scene Y-position reverses over 2.5s: -1.2 -> 0
        scene.position.y = targetY * (1 - transEased);

        camera.updateProjectionMatrix();
      } else {
        // Restore subtractive negative filter blending during normal idle view
        if (planetMaterial.blending !== THREE.CustomBlending) {
          planetMaterial.blending = THREE.CustomBlending;
          planetMaterial.blendEquation = THREE.SubtractEquation;
          planetMaterial.blendSrc = THREE.SrcAlphaFactor;
          planetMaterial.blendDst = THREE.OneFactor;
          planetMaterial.needsUpdate = true;

          planetMaterial2.blending = THREE.CustomBlending;
          planetMaterial2.blendEquation = THREE.SubtractEquation;
          planetMaterial2.blendSrc = THREE.SrcAlphaFactor;
          planetMaterial2.blendDst = THREE.OneFactor;
          planetMaterial2.needsUpdate = true;
        }

        // Bezier FOV, Tilt & Y-Shift Animation: Starts off at FOV=3 & 15 deg tilt, expanding to FOV=75 & 0 deg tilt & 10% lower position over 2s
        const elapsedFov = performance.now() - fovStartTime;
        if (elapsedFov <= FOV_ANIMATION_DURATION) {
          const progress = Math.min(1, elapsedFov / FOV_ANIMATION_DURATION);
          // Smooth Cubic-Bezier Easing Curve
          const easedProgress = progress < 0.5
            ? 4 * progress * progress * progress
            : 1 - Math.pow(-2 * progress + 2, 3) / 2;

          camera.fov = 3 + (75 - 3) * easedProgress;
          camera.rotation.z = initialTilt * (1 - easedProgress);
          scene.position.y = targetY * easedProgress;
          camera.updateProjectionMatrix();
        } else if (camera.fov !== 75 || camera.rotation.z !== 0 || scene.position.y !== targetY) {
          camera.fov = 75;
          camera.rotation.z = 0;
          scene.position.y = targetY;
          camera.updateProjectionMatrix();
        }
      }

      // Smoothly decay scroll acceleration boost
      scrollBoost *= 0.94;
      if (scrollBoost < 0.0001) scrollBoost = 0;

      // Calculate depth factor based on distance to camera (closer = slower, further = faster)
      const depthFactor1 = 1 - Math.sin(angle1) * 0.8;
      const depthFactor2 = 1 - Math.sin(angle2) * 0.8;

      const currentSpeed1 = (orbitSpeed1 * speedMult + scrollBoost) * depthFactor1;
      const currentSpeed2 = (orbitSpeed2 * speedMult + scrollBoost * 0.5) * depthFactor2;

      angle1 += currentSpeed1;
      planet.position.x = Math.cos(angle1) * orbitRadius;
      planet.position.z = Math.sin(angle1) * orbitRadius;

      angle2 += currentSpeed2;
      planet2.position.x = Math.cos(angle2) * orbitRadius2;
      planet2.position.z = Math.sin(angle2) * orbitRadius2;

      // Dynamic Thick Tapered Solid White Ribbon Trail Growth (Grows with planetary speed during scan transition)
      if (transRef.current.active) {
        ribbonMat1.opacity = 1.0;
        ribbonMat2.opacity = 1.0;

        const transElapsed = performance.now() - transRef.current.startTime;
        const transProgress = Math.min(1, transElapsed / TRANSITION_DURATION);
        const trailArc = transProgress * Math.PI * 4.5;

        // Update Ribbon 1 (Planet 1: start width 0.22 -> end width 0.01)
        const pos1 = ribbonMesh1.geometry.attributes.position.array as Float32Array;
        const startW1 = 0.22;
        for (let i = 0; i < RIBBON_SEGMENTS; i++) {
          const t = i / (RIBBON_SEGMENTS - 1);
          const sampleAngle = angle1 - t * trailArc;
          const currentW = startW1 * Math.pow(1 - t, 1.2);

          const cx = Math.cos(sampleAngle) * orbitRadius;
          const cz = Math.sin(sampleAngle) * orbitRadius;

          // Upper vertex
          pos1[i * 6 + 0] = cx;
          pos1[i * 6 + 1] = currentW * 0.5;
          pos1[i * 6 + 2] = cz;

          // Lower vertex
          pos1[i * 6 + 3] = cx;
          pos1[i * 6 + 4] = -currentW * 0.5;
          pos1[i * 6 + 5] = cz;
        }
        ribbonMesh1.geometry.attributes.position.needsUpdate = true;

        // Update Ribbon 2 (Planet 2: start width 0.32 -> end width 0.01)
        const pos2 = ribbonMesh2.geometry.attributes.position.array as Float32Array;
        const startW2 = 0.32;
        for (let i = 0; i < RIBBON_SEGMENTS; i++) {
          const t = i / (RIBBON_SEGMENTS - 1);
          const sampleAngle = angle2 - t * trailArc;
          const currentW = startW2 * Math.pow(1 - t, 1.2);

          const cx = Math.cos(sampleAngle) * orbitRadius2;
          const cz = Math.sin(sampleAngle) * orbitRadius2;

          // Upper vertex
          pos2[i * 6 + 0] = cx;
          pos2[i * 6 + 1] = currentW * 0.5;
          pos2[i * 6 + 2] = cz;

          // Lower vertex
          pos2[i * 6 + 3] = cx;
          pos2[i * 6 + 4] = -currentW * 0.5;
          pos2[i * 6 + 5] = cz;
        }
        ribbonMesh2.geometry.attributes.position.needsUpdate = true;
      } else {
        ribbonMat1.opacity = 0;
        ribbonMat2.opacity = 0;
      }

      const scale = 1 + Math.sin(Date.now() * 0.0015) * 0.03;
      star.scale.set(scale, scale, scale);

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!containerRef.current) return;
      width = containerRef.current.clientWidth;
      height = containerRef.current.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('wheel', handleWheel);
      cancelAnimationFrame(animationFrameId);
      container.removeChild(renderer.domElement);
      renderer.dispose();
      starGeometry.dispose();
      starMaterial.dispose();
      planetGeometry.dispose();
      planetMaterial.dispose();
      orbitPathGeometry.dispose();
      orbitPathMaterial.dispose();
      planetGeometry2.dispose();
      planetMaterial2.dispose();
      orbitPathGeometry2.dispose();
      orbitPathMaterial2.dispose();
    };
  }, []);

  return <div ref={containerRef} className="absolute inset-0 w-full h-full bg-transparent pointer-events-none" />;
};
