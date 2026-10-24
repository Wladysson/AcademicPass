package org.enade.simulado.presentation.dto;

import org.enade.simulado.domain.model.ExportStatus;
import java.time.Instant;

public class SimuladoExportResponseDto {

    private String exportId;
    private ExportStatus status;
    private String message;
    private Instant requestedAt;

    public SimuladoExportResponseDto() {
    }

    public SimuladoExportResponseDto(
            String exportId,
            ExportStatus status,
            String message,
            Instant requestedAt
    ) {
        this.exportId = exportId;
        this.status = status;
        this.message = message;
        this.requestedAt = requestedAt;
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

    public Instant getRequestedAt() {
        return requestedAt;
    }

    public void setRequestedAt(Instant requestedAt) {
        this.requestedAt = requestedAt;
    }
}