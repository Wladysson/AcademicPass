package org.enade.simulado.presentation.dto;

import org.enade.simulado.domain.model.ExportStatus;

import java.time.Instant;

public class SimuladoStatusResponseDto {

    private String exportId;
    private ExportStatus status;
    private String message;
    private String fileUrl;
    private String fileName;
    private String contentType;
    private Long fileSize;
    private Instant requestedAt;
    private Instant updatedAt;

    public SimuladoStatusResponseDto() {
    }

    public SimuladoStatusResponseDto(
            String exportId,
            ExportStatus status,
            String message,
            String fileUrl,
            String fileName,
            String contentType,
            Long fileSize,
            Instant requestedAt,
            Instant updatedAt
    ) {
        this.exportId = exportId;
        this.status = status;
        this.message = message;
        this.fileUrl = fileUrl;
        this.fileName = fileName;
        this.contentType = contentType;
        this.fileSize = fileSize;
        this.requestedAt = requestedAt;
        this.updatedAt = updatedAt;
    }

    public String getExportId() {
        return exportId;
    }

    public void setExportId(String exportId) {
        this.exportId = exportId;
    }

    public ExportStatus getStatus() {
        return status;
    }

    public void setStatus(ExportStatus status) {
        this.status = status;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getFileUrl() {
        return fileUrl;
    }

    public void setFileUrl(String fileUrl) {
        this.fileUrl = fileUrl;
    }

    public String getFileName() {
        return fileName;
    }

    public void setFileName(String fileName) {
        this.fileName = fileName;
    }

    public String getContentType() {
        return contentType;
    }

    public void setContentType(String contentType) {
        this.contentType = contentType;
    }

    public Long getFileSize() {
        return fileSize;
    }

    public void setFileSize(Long fileSize) {
        this.fileSize = fileSize;
    }

    public Instant getRequestedAt() {
        return requestedAt;
    }

    public void setRequestedAt(Instant requestedAt) {
        this.requestedAt = requestedAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }
}