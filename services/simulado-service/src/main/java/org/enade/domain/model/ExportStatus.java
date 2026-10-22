package br.org.enade.simulado.domain.model;

public enum ExportStatus {

    REQUESTED,
    PROCESSING,
    COMPLETED,
    FAILED;

    public boolean isTerminal() {
        return this == COMPLETED || this == FAILED;
    }

    public boolean canTransitionTo(ExportStatus nextStatus) {
        if (nextStatus == null || isTerminal()) {
            return false;
        }

        return switch (this) {
            case REQUESTED ->
                    nextStatus == PROCESSING || nextStatus == FAILED;
            case PROCESSING ->
                    nextStatus == COMPLETED || nextStatus == FAILED;
            case COMPLETED, FAILED -> false;
        };
    }
}