import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

export default function ImageUpload({ onUpload, isLoading }) {
  const onDrop = useCallback(
    (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        onUpload(acceptedFiles[0]);
      }
    },
    [onUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
    },
    maxSize: 10 * 1024 * 1024, // 10MB
    multiple: false,
    disabled: isLoading,
  });

  return (
    <div className="upload-container">
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? 'active' : ''} ${
          isLoading ? 'disabled' : ''
        }`}
      >
        <input {...getInputProps()} />
        <div className="dropzone-content">
          <svg
            className="upload-icon"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
          {isLoading ? (
            <p>Analyzing roof image...</p>
          ) : isDragActive ? (
            <p>Drop the image here...</p>
          ) : (
            <>
              <p>Drag and drop a roof image here</p>
              <p className="upload-hint">or click to browse</p>
              <p className="upload-limit">JPG or PNG, max 10MB</p>
            </>
          )}
        </div>
      </div>
      {isLoading && (
        <div className="loading-indicator">
          <div className="spinner"></div>
          <p>Analyzing image... This typically takes 3-5 seconds</p>
        </div>
      )}
    </div>
  );
}
