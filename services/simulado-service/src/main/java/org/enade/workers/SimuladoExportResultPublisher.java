package org.enade.simulado.workers;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.reactive.messaging.Channel;
import org.eclipse.microprofile.reactive.messaging.Emitter;
import org.jboss.logging.Logger;

import java.time.Instant;

@ApplicationScoped
public class SimuladoExportResultPublisher {

    private static final Logger LOG =
            Logger.getLogger(SimuladoExportResultPublisher.class);

    @Inject
    ObjectMapper objectMapper;

    @Inject
    @Channel("simulado-export-result")
    Emitter<String> resultEmitter;

    public void publicarSucesso(String exportId, String simuladoId) {
        validarExportId(exportId);

        publicar(new SimuladoExportResultEvent(
                exportId,
                simuladoId,
                "COMPLETED",
                null,
                Instant.now()
        ));
    }

    public void publicarFalha(String exportId, String errorMessage) {
        validarExportId(exportId);

        publicar(new SimuladoExportResultEvent(
                exportId,
                null,
                "FAILED",
                normalizarMensagem(errorMessage),
                Instant.now()
        ));
    }

    private void publicar(SimuladoExportResultEvent event) {
        try {
            String payload = objectMapper.writeValueAsString(event);
            resultEmitter.send(payload)
                    .whenComplete((ignored, failure) -> {
                        if (failure != null) {
                            LOG.errorf(
                                    failure,
                                    "Falha ao publicar resultado da exportação. exportId=%s",
                                    event.exportId()
                            );
                        } else {
                            LOG.infof(
                                    "Resultado da exportação publicado. exportId=%s, status=%s",
                                    event.exportId(),
                                    event.status()
                            );
                        }
                    });
        } catch (JsonProcessingException exception) {
            LOG.errorf(
                    exception,
                    "Falha ao serializar resultado da exportação. exportId=%s",
                    event.exportId()
            );

            throw new IllegalStateException(
                    "Não foi possível serializar o resultado da exportação.",
                    exception
            );
        }
    }

    private void validarExportId(String exportId) {
        if (exportId == null || exportId.isBlank()) {
            throw new IllegalArgumentException(
                    "O identificador da exportação é obrigatório."
            );
        }
    }

    private String normalizarMensagem(String message) {
        if (message == null || message.isBlank()) {
            return "Falha inesperada durante a exportação do simulado.";
        }

        return message;
    }

    public record SimuladoExportResultEvent(
            String exportId,
            String simuladoId,
            String status,
            String errorMessage,
            Instant occurredAt
    ) {
    }
}