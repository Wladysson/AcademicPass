package br.org.enade.simulado.domain.model;

public enum ExportFormat {

    PDF("application/pdf", "pdf"),
    JSON("application/json", "json");

    private final String contentType;
    private final String fileExtension;

    ExportFormat(String contentType, String fileExtension) {
        this.contentType = contentType;
        this.fileExtension = fileExtension;
    }

    public String getContentType() {
        return contentType;
    }

    public String getFileExtension() {
        return fileExtension;
    }
}