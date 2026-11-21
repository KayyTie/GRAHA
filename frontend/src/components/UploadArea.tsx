import React, { useState, useRef } from 'react';
import { Upload, File, AlertTriangle, FolderOpen } from 'lucide-react';

interface UploadAreaProps {
  onFileLoaded: (file: File | string) => void;
  onFilesLoaded?: (files: File[]) => void;
  isLoading: boolean;
  mode?: 'single' | 'batch' | 'folder';
  leftTabs?: React.ReactNode;
  rightTabs?: React.ReactNode;
}

export const UploadArea: React.FC<UploadAreaProps> = ({
  onFileLoaded,
  onFilesLoaded,
  isLoading,
  mode = 'single',
  leftTabs,
  rightTabs
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<{ name: string; size: number } | null>(null);
  const [batchCount, setBatchCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const validateFile = (file: File): boolean => {
    const validExtensions = ['.fits', '.fit', '.fits.gz'];
    const fileName = file.name.toLowerCase();
    const isValid = validExtensions.some(ext => fileName.endsWith(ext));

    if (!isValid) {
      setError("Invalid file type. Please upload a calibrated TESS FITS file (.fits, .fit, .fits.gz).");
      setSelectedFile(null);
      return false;
    }

    setError(null);
    setSelectedFile({ name: file.name, size: file.size });
    return true;
  };

  const validateMultipleFiles = (fileList: FileList): File[] => {
    const validExtensions = ['.fits', '.fit', '.fits.gz'];
    const validFiles: File[] = [];

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      if (validExtensions.some(ext => file.name.toLowerCase().endsWith(ext))) {
        validFiles.push(file);
      }
    }
    return validFiles;
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      if (mode === 'batch' || mode === 'folder') {
        const files = validateMultipleFiles(e.dataTransfer.files);
        if (files.length > 0) {
          setError(null);
          setBatchCount(files.length);
          if (onFilesLoaded) onFilesLoaded(files);
        } else {
          setError("No valid FITS files found in selection.");
        }
      } else {
        const file = e.dataTransfer.files[0];
        if (validateFile(file)) {
          onFileLoaded(file);
        }
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      if (mode === 'batch' || mode === 'folder') {
        const files = validateMultipleFiles(e.target.files);
        if (files.length > 0) {
          setError(null);
          setBatchCount(files.length);
          if (onFilesLoaded) onFilesLoaded(files);
        } else {
          setError("No valid FITS files found in selection.");
        }
      } else {
        const file = e.target.files[0];
        if (validateFile(file)) {
          onFileLoaded(file);
        }
      }
    }
  };

  const triggerInputClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="bg-transparent text-black w-full h-full flex flex-col justify-between p-4">
      {/* Single Dotted Upload Box containing Left Tabs, Center Dropzone, Right Tabs */}
      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-3xl p-6 transition-all duration-300 flex items-stretch gap-6 flex-grow relative ${dragActive
          ? 'border-black bg-neutral-200 scale-[1.01]'
          : (selectedFile || batchCount)
            ? 'border-black/60 bg-neutral-100'
            : 'border-black/30 hover:border-black bg-neutral-100 hover:bg-neutral-200/80 shadow-sm'
          }`}
      >
        {/* Left Tabs inside Dotted Box */}
        {leftTabs && (
          <div className="flex flex-col justify-center space-y-4 w-44 shrink-0 z-20" onClick={(e) => e.stopPropagation()}>
            {leftTabs}
          </div>
        )}

        {/* Center Content Dropzone */}
        <div
          onClick={triggerInputClick}
          className="flex-grow flex flex-col justify-between items-center text-center cursor-pointer py-4 px-4 z-10"
        >
          {/* Title and Description inside top of center dropzone */}
          <div>
            <h2 className="text-3xl font-orbitron tracking-widest text-black uppercase mb-2 flex items-center justify-center space-x-4">
              {mode === 'folder' ? (
                <FolderOpen className="w-8 h-8 text-black stroke-[2]" />
              ) : (
                <Upload className="w-8 h-8 text-black stroke-[2]" />
              )}
              <span>
                {mode === 'folder' && 'TESS FITS Folder Ingestion'}
                {mode === 'batch' && 'TESS FITS Batch Processing'}
                {mode === 'single' && 'TESS FITS Curve Upload'}
              </span>
            </h2>
            <p className="text-base text-black/60 font-mono leading-relaxed max-w-xl mx-auto">
              {mode === 'folder' && 'Select a folder containing NASA TESS FITS curves to run batch exoplanet classification and generate a CSV summary.'}
              {mode === 'batch' && 'Select or drag & drop multiple TESS FITS files to run batch exoplanet classification and generate a CSV summary.'}
              {mode === 'single' && 'Drag and drop a calibrated TESS light curve FITS file to run the AI exoplanet detection pipeline.'}
            </p>
          </div>

          {mode === 'folder' ? (
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              {...({
                webkitdirectory: "",
                directory: "",
                multiple: true
              } as any)}
              onChange={handleFileChange}
              disabled={isLoading}
            />
          ) : (
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".fits,.fit,.fits.gz"
              multiple={mode === 'batch'}
              onChange={handleFileChange}
              disabled={isLoading}
            />
          )}

          {batchCount !== null ? (
            <div className="flex flex-col items-center space-y-6 my-auto">
              <FolderOpen className="w-20 h-20 text-black stroke-[1.5]" />
              <div className="text-black text-xl font-bold font-mono">{batchCount} FITS Files Loaded</div>
              <div className="text-sm px-6 py-2 bg-black text-white rounded-full font-bold uppercase tracking-widest font-orbitron shadow">
                Ready to Process
              </div>
            </div>
          ) : selectedFile ? (
            <div className="flex flex-col items-center space-y-6 my-auto">
              <File className="w-20 h-20 text-black stroke-[1.5]" />
              <div className="text-black text-xl font-bold break-all max-w-2xl font-mono">{selectedFile.name}</div>
              <div className="text-base text-black/60 font-mono">
                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
              </div>
              <div className="text-sm px-6 py-2 bg-black text-white rounded-full font-bold uppercase tracking-widest font-orbitron shadow">
                File Validated
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center space-y-6 my-auto text-black/70">
              {mode === 'folder' ? (
                <FolderOpen className="w-20 h-20 text-black animate-bounce stroke-[1.5]" />
              ) : (
                <Upload className="w-20 h-20 text-black animate-bounce stroke-[1.5]" />
              )}
              <span className="font-bold text-black text-2xl font-mono">
                {mode === 'folder' ? 'Choose Folder to Upload' : 'Choose files or drag & drop here'}
              </span>
              <span className="text-base text-black/60 font-mono">Supports .fits, .fit, .fits.gz</span>
            </div>
          )}

          <div />
        </div>

        {/* Right Tabs inside Dotted Box */}
        {rightTabs && (
          <div className="flex flex-col justify-center space-y-4 w-44 shrink-0 z-20" onClick={(e) => e.stopPropagation()}>
            {rightTabs}
          </div>
        )}
      </div>

      {error && (
        <div className="mt-3 p-3 bg-red-50 border border-red-300 rounded-2xl flex items-start space-x-3 text-sm text-red-900 font-mono shrink-0">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5 text-red-600" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};
