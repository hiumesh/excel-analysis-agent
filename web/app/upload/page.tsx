"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { FileUpload } from "@/components/FileUpload";
import { uploadDefaultFile, type UploadResult } from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ArrowLeft, CheckCircle2 } from "lucide-react";

export default function UploadPage() {
  const router = useRouter();
  const [uploadedFile, setUploadedFile] = useState<UploadResult | null>(null);

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border/40 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto max-w-4xl flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.push("/")}
              className="mr-2 h-8 w-8 rounded-full hover:bg-muted/50"
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div className="flex items-center justify-center">
              <Image
                src="/isb_identity_colour_rgb_positive.svg"
                alt="ISB Logo"
                width={80}
                height={40}
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-6 py-12">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-foreground tracking-tight mb-2">
              Configure Global Default Source
            </h1>
            <p className="text-muted-foreground text-sm">
              Upload an Excel (.xlsx, .xls) or CSV file to be used as the default dataset for all analysis sessions. This replaces the existing default file and persists across server restarts.
            </p>
          </div>

          <div className="bg-card border border-border/50 rounded-2xl p-6 shadow-sm">
            {uploadedFile ? (
              <div className="flex flex-col items-center justify-center py-8 text-center animate-in fade-in duration-500">
                <div className="h-16 w-16 mb-4 rounded-full bg-emerald-500/10 flex items-center justify-center">
                  <CheckCircle2 className="h-8 w-8 text-emerald-500" />
                </div>
                <h3 className="text-lg font-medium text-foreground mb-1">Upload Successful!</h3>
                <p className="text-sm text-muted-foreground mb-6">
                  <strong className="text-foreground">{uploadedFile.filename}</strong> is now the global default dataset.
                </p>
                <div className="flex gap-3">
                  <Button 
                    variant="outline" 
                    onClick={() => setUploadedFile(null)}
                  >
                    Upload Another
                  </Button>
                  <Button onClick={() => router.push("/")}>
                    Return to Chat
                  </Button>
                </div>
              </div>
            ) : (
              <FileUpload
                onFileUploaded={(result) => setUploadedFile(result)}
                onFileRemoved={() => setUploadedFile(null)}
                uploadedFile={uploadedFile}
                uploadAction={uploadDefaultFile}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
