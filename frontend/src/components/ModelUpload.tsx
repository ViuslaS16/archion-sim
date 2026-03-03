"use client";

import { useCallback, useRef, useState } from "react";
import { CloudUpload, FileWarning, CheckCircle } from "lucide-react";
import type { GeometryData } from "@/types/simulation";

const ALLOWED_EXTENSIONS = [".obj", ".glb", ".gltf"];

type UploadStatus = "idle" | "uploading" | "success" | "error";

interface ModelUploadProps {
  onUploadComplete: (data: GeometryData) => void;
  apiUrl: string;
}

export default function ModelUpload({
  onUploadComplete,
  apiUrl,
}: ModelUploadProps) {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Invalid file type "${ext}". Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`;
    }
    return null;
  };

  const uploadFile = useCallback(
    async (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        setStatus("error");
        setError(validationError);
        return;
      }

      setStatus("uploading");
      setProgress(0);
      setError(null);

      const formData = new FormData();
      formData.append("file", file);

      try {
        const xhr = new XMLHttpRequest();

        const result = await new Promise<GeometryData>((resolve, reject) => {
          xhr.upload.addEventListener("progress", (e) => {
            if (e.lengthComputable) {
              setProgress(Math.round((e.loaded / e.total) * 100));
            }
          });

          xhr.addEventListener("load", () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              resolve(JSON.parse(xhr.responseText));
            } else {
              let msg = `Upload failed (HTTP ${xhr.status})`;
              try {
                const body = JSON.parse(xhr.responseText);
                if (body.detail) msg = body.detail;
              } catch {
                /* keep default message */
              }
              reject(new Error(msg));
            }
          });

          xhr.addEventListener("error", () =>
            reject(new Error("Network error — is the backend running?")),
          );

          xhr.open("POST", `${apiUrl}/api/process-model`);
          xhr.send(formData);
        });

        setStatus("success");
        setProgress(100);
        onUploadComplete(result);
      } catch (err) {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    },
    [apiUrl, onUploadComplete],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) uploadFile(file);
    },
    [uploadFile],
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) uploadFile(file);
      // Reset so the same file can be re-selected
      e.target.value = "";
    },
    [uploadFile],
  );

  return (
    <div className="w-full max-w-xl">
      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`
          flex flex-col items-center justify-center gap-3
          rounded-xl border-2 border-dashed p-10
          cursor-pointer transition-all duration-200
          ${
            dragOver
              ? "border-cyan-400 bg-cyan-400/10"
              : status === "error"
                ? "border-red-500/50 bg-red-500/5"
                : status === "success"
                  ? "border-green-500/50 bg-green-500/5"
                  : "border-zinc-700 bg-zinc-900 hover:border-zinc-500 hover:bg-zinc-800/50"
          }
        `}
      >
        {status === "success" ? (
          <CheckCircle className="h-10 w-10 text-green-400" />
        ) : status === "error" ? (
          <FileWarning className="h-10 w-10 text-red-400" />
        ) : (
          <CloudUpload
            className={`h-10 w-10 ${dragOver ? "text-cyan-400" : "text-zinc-500"}`}
          />
        )}

        <div className="text-center">
          {status === "uploading" ? (
            <p className="text-sm text-zinc-400">Processing model…</p>
          ) : status === "success" ? (
            <p className="text-sm text-green-400">
              Model processed — drop another to replace
            </p>
          ) : (
            <>
              <p className="text-sm font-medium text-zinc-300">
                Drag & drop a 3D model here
              </p>
              <p className="text-xs text-zinc-500 mt-1">
                or click to browse — .obj, .glb, .gltf
              </p>
            </>
          )}
        </div>

        <input
          ref={inputRef}
          type="file"
          accept=".obj,.glb,.gltf"
          onChange={handleFileInput}
          className="hidden"
        />
      </div>

      {/* Progress bar */}
      {status === "uploading" && (
        <div className="mt-3 w-full rounded-full bg-zinc-800 h-2 overflow-hidden">
          <div
            className="h-full bg-cyan-500 transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {/* Error toast */}
      {status === "error" && error && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3">
          <FileWarning className="h-4 w-4 text-red-400 mt-0.5 shrink-0" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}
    </div>
  );
}
