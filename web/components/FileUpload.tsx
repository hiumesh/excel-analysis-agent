"use client";

import { useState, useCallback, useRef } from "react";
import { cn } from "@/lib/utils";
import {
  Upload,
  FileSpreadsheet,
  X,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { uploadFile, UploadResult } from "@/lib/api";

interface FileUploadProps {
  onFileUploaded: (result: UploadResult) => void;
  onFileRemoved: () => void;
  uploadedFile: UploadResult | null;
  disabled?: boolean;
  className?: string;
  uploadAction?: (file: File) => Promise<UploadResult>;
}

export function FileUpload({
  onFileUploaded,
  onFileRemoved,
  uploadedFile,
  disabled = false,
  className,
  uploadAction = uploadFile,
}: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = useCallback((file: File): boolean => {
    const ACCEPTED_TYPES = [
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "application/vnd.ms-excel",
      "text/csv",
    ];
    const ACCEPTED_EXTENSIONS = [".xlsx", ".xls", ".csv"];

    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
    if (
      !ACCEPTED_EXTENSIONS.includes(ext) &&
      !ACCEPTED_TYPES.includes(file.type)
    ) {
      setError("Please upload an Excel (.xlsx, .xls) or CSV (.csv) file");
      return false;
    }
    if (file.size > 50 * 1024 * 1024) {
      setError("File size must be under 50MB");
      return false;
    }
    return true;
  }, []);

  const handleUpload = useCallback(
    async (file: File) => {
      if (!validateFile(file)) return;
      setError(null);
      setIsUploading(true);
      try {
        const result = await uploadAction(file);
        onFileUploaded(result);
      } catch (err) {
        setError((err as Error).message || "Upload failed");
      } finally {
        setIsUploading(false);
      }
    },
    [onFileUploaded, uploadAction, validateFile],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled || isUploading) return;
      const file = e.dataTransfer.files[0];
      if (file) handleUpload(file);
    },
    [disabled, isUploading, handleUpload],
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled && !isUploading) setIsDragging(true);
    },
    [disabled, isUploading],
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleClick = () => {
    if (!disabled && !isUploading) fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    e.target.value = "";
  };

  // Compact chip when file is already uploaded
  if (uploadedFile) {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        <Badge
          variant="secondary"
          className="flex items-center gap-2 py-1.5 px-3 text-sm font-normal bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/15 transition-colors"
        >
          <CheckCircle2 className="h-3.5 w-3.5" />
          <FileSpreadsheet className="h-3.5 w-3.5" />
          <span className="max-w-[200px] truncate">
            {uploadedFile.filename}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onFileRemoved();
            }}
            className="ml-1 rounded-full p-0.5 hover:bg-emerald-500/20 transition-colors"
            disabled={disabled}
          >
            <X className="h-3 w-3" />
          </button>
        </Badge>
      </div>
    );
  }

  return (
    <div className={cn("w-full", className)}>
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
        className={cn(
          "relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 cursor-pointer transition-all duration-300",
          isDragging
            ? "border-primary/60 bg-primary/5 scale-[1.01]"
            : "border-border/50 bg-muted/20 hover:border-primary/30 hover:bg-muted/30",
          (disabled || isUploading) && "opacity-50 cursor-not-allowed",
          error && "border-destructive/50",
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          onChange={handleFileChange}
          className="hidden"
          disabled={disabled || isUploading}
        />

        {isUploading ? (
          <>
            <Loader2 className="h-8 w-8 text-primary animate-spin" />
            <p className="text-sm text-muted-foreground">Uploading file...</p>
          </>
        ) : (
          <>
            <div className="rounded-full bg-primary/10 p-3">
              <Upload className="h-6 w-6 text-primary/70" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-foreground/80">
                Drop your file here or click to browse
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Supports Excel (.xlsx, .xls) and CSV files up to 50MB
              </p>
            </div>
          </>
        )}
      </div>

      {error && (
        <p className="mt-2 text-xs text-destructive animate-in fade-in slide-in-from-top-1">
          {error}
        </p>
      )}
    </div>
  );
}
