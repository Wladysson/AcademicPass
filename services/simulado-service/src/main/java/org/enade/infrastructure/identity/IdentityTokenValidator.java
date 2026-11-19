package org.enade.simulado.infrastructure.kafka;

import org.enade.simulado.domain.exception.SimuladoExportException;
import org.enade.simulado.presentation.dto.SimuladoExportRequestDto;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.smallrye.reactive.messaging.MutinyEmitter;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.reactive.messaging.Channel;
import org.jboss.logging.Logger;

import java.time.Instant;
import java.util.UUID;

@ApplicationScoped
public class SimuladoExportRequestProducer {

    private static final Logger LOG =
            Logger.getLogger(SimuladoExportRequestProducer.class);

    @Inject
    ObjectMapper objectMapper;

    @Inject
    @Channel("simulado-export-requested")
    MutinyEmitter<String> emitter;

    public void publicar(
            UUID exportId,
            SimuladoExportRequestDto request,
            Instant requestedAt
    ) {
        if (exportId == null || request == null || requestedAt == null) {
            throw new SimuladoExportException(
                    "Os dados da solicitação de exportação são obrigatórios."
            );
        }

        SimuladoExportRequestEvent event = new SimuladoExportRequestEvent(
                exportId.toString(),
                request,
                requestedAt
        );

        try {
            String payload = objectMapper.writeValueAsString(event);

            emitter.sendMessage(payload)
                    .subscribe()
                    .with(
                            ignored -> LOG.debugf(
                                    "Solicitação de exportação publicada: %s",
                                    exportId
                            ),
                            failure -> LOG.errorf(
                                    failure,
                                    "Falha ao publicar a solicitação de exportação %s",
                                    exportId
                            )
                    );
        } catch (JsonProcessingException exception) {
            throw new SimuladoExportException(
                    "Não foi possível serializar a solicitação de exportação.",
                    exception
            );
        }
    }

    public record SimuladoExportRequestEvent(
            String exportId,
            SimuladoExportRequestDto request,
            Instant requestedAt
    ) {
    }
}