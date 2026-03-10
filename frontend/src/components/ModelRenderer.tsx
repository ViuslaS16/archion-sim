"use client";

import { Suspense, useEffect, useRef } from "react";
import { useLoader } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";

// Hex values for common blue/teal placeholder colors to filter out
const PLACEHOLDER_COLORS = new Set([
  0x008b8b, // DarkCyan
  0x0080ff, // Azure
  0x0891b2, // teal-500
  0x06b6d4, // cyan-500
  0x22d3ee, // cyan-400
  0x2a2a4a, // dark blue-purple (our floor color)
  0x1a1a3a, // overlay floor color
]);

function isPlaceholderColor(hex: number): boolean {
  // Check exact matches
  if (PLACEHOLDER_COLORS.has(hex)) return true;
  // Check if in the teal/cyan family (hue ~170-200, high saturation)
  const r = (hex >> 16) & 0xff;
  const g = (hex >> 8) & 0xff;
  const b = hex & 0xff;
  // Teal: low red, medium-high green, high blue
  if (r < 30 && g > 100 && b > 150) return true;
  return false;
}

function filterPlaceholderMeshes(root: THREE.Object3D) {
  root.traverse((obj) => {
    if (!(obj instanceof THREE.Mesh)) return;
    const mat = obj.material as THREE.MeshStandardMaterial;
    if (!mat?.color) return;

    const hex = mat.color.getHex();
    if (isPlaceholderColor(hex)) {
      obj.visible = false;
      console.log(
        `[ModelRenderer] Hiding placeholder mesh: "${obj.name}" (color: #${hex.toString(16).padStart(6, "0")})`,
      );
    }
  });
}

/**
 * Compute XZ offset to align the 3D model with boundary coordinates.
 *
 * The geometry pipeline centers boundaries by subtracting centerOffset [cx, cy]
 * in its 2D space (X, Y after Z-up rotation). For GLB/GLTF (Y-up in Three.js),
 * the mapping is: pipeline X → Three.js X, pipeline Y → Three.js -Z.
 *
 * So to align, we shift the model by (-cx, ?, cy) — i.e. the same centering
 * the geometry pipeline applied, but mapped to Three.js axes.
 */
/**
 * Ground the 3D model exactly at Y=0 (the simulation grid plane).
 * -box.min.y lifts the lowest vertex of the model to exactly Y=0.
 * XZ is aligned using the backend's centerOffset [cx, cy].
 * Pipeline 2D axes: X→X, Y→-Z (because Three.js Z is depth, backend Y is depth).
 */
function computeAlignedPosition(
  root: THREE.Object3D,
  centerOffset?: [number, number],
): THREE.Vector3 {
  const box = new THREE.Box3().setFromObject(root);
  // Lift: move the model so its absolute bottom is at Y=0
  const groundY = -box.min.y;

  if (centerOffset) {
    const [cx, cy] = centerOffset;
    // Shift XZ: undo the centering the backend applied
    return new THREE.Vector3(-cx, groundY, cy);
  }

  // Fallback: center on XZ using bounding box
  const center = box.getCenter(new THREE.Vector3());
  return new THREE.Vector3(-center.x, groundY, -center.z);
}

// ---------------------------------------------------------------------------
// GltfModel — loads .glb / .gltf via drei's useGLTF
// ---------------------------------------------------------------------------

function GltfModel({
  url,
  centerOffset,
}: {
  url: string;
  centerOffset?: [number, number];
}) {
  const { scene } = useGLTF(url);
  const groupRef = useRef<THREE.Group>(null);

  useEffect(() => {
    if (!groupRef.current) return;

    // Reset to origin BEFORE computing bounds — setFromObject uses world-space
    // coordinates, so if the scene was already moved (e.g. by React Strict
    // Mode's double-effect), the bounding box would include the previous offset
    // and cancel the lift.
    scene.position.set(0, 0, 0);

    // Filter out blue/teal placeholder meshes
    filterPlaceholderMeshes(scene);

    // Align model XZ with boundary coordinates, ground at Y=MODEL_Y_LIFT
    const pos = computeAlignedPosition(scene, centerOffset);
    scene.position.copy(pos);
  }, [scene, centerOffset]);

  return (
    <group ref={groupRef}>
      <primitive object={scene} />
    </group>
  );
}

// ---------------------------------------------------------------------------
// ObjModel — loads .obj via Three's OBJLoader
// ---------------------------------------------------------------------------

function ObjModel({
  url,
  centerOffset,
}: {
  url: string;
  centerOffset?: [number, number];
}) {
  const obj = useLoader(OBJLoader, url);
  const groupRef = useRef<THREE.Group>(null);

  useEffect(() => {
    if (!groupRef.current) return;

    // Reset to origin before computing bounds (same reason as GltfModel)
    obj.position.set(0, 0, 0);

    // Apply fallback material where none exists
    const fallbackMat = new THREE.MeshStandardMaterial({
      color: "#8899aa",
      roughness: 0.6,
      metalness: 0.2,
    });

    obj.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        if (
          !child.material ||
          (child.material as THREE.Material).type === "MeshBasicMaterial"
        ) {
          child.material = fallbackMat;
        }
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });

    // Filter out blue/teal placeholder meshes
    filterPlaceholderMeshes(obj);

    // Align model XZ with boundary coordinates, ground at Y=0
    const pos = computeAlignedPosition(obj, centerOffset);
    obj.position.copy(pos);
  }, [obj, centerOffset]);

  return (
    <group ref={groupRef}>
      <primitive object={obj} />
    </group>
  );
}

// ---------------------------------------------------------------------------
// ModelRenderer — public entry point, picks the right loader
// ---------------------------------------------------------------------------

interface ModelRendererProps {
  url: string;
  format: "obj" | "glb" | "gltf";
  centerOffset?: [number, number];
}

export default function ModelRenderer({ url, format, centerOffset }: ModelRendererProps) {
  return (
    <Suspense fallback={null}>
      {format === "obj" ? (
        <ObjModel url={url} centerOffset={centerOffset} />
      ) : (
        <GltfModel url={url} centerOffset={centerOffset} />
      )}
    </Suspense>
  );
}
