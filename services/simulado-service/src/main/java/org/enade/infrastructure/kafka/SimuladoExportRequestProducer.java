package org.enade.simulado.infrastructure.kafka;

import org.enade.simulado.application.SimuladoGenerationUseCase;
import org.enade.simulado.domain.exception.SimuladoExportException;
import org.enade.simulado.presentation.dto.SimuladoExportRequestDto;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.smallrye.reactive.messaging.annotations.Blocking;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.reactive.messaging.Incoming;
import org.jboss.logging.Logger;

import java.time.Instant;

@ApplicationScoped
public class SimuladoExportRequestConsumer {

    private static final Logger LOG =
            Logger.getLogger(SimuladoExportRequestConsumer.class);

    @Inject
    ObjectMapper objectMapper;

    @Inject
    SimuladoGenerationUseCase simuladoGenerationUseCase;

    @Incoming("simulado-export-requested")
    @Blocking
    public void consumir(String payload) {
        if (payload == null || payload.isBlank()) {
            throw new SimuladoExportException(
                    "O evento de solicitação de exportação está vazio."
            );
        }

        SimuladoExportRequestProducer.SimuladoExportRequestEvent event;

        try {
            event = objectMapper.readValue(
                    payload,
                    SimuladoExportRequestProducer.SimuladoExportRequestEvent.class
            );
        } catch (Exception exception) {
            LOG.error("Não foi possível interpretar o evento de exportação.", exception);

            throw new SimuladoExportException(
                    "O evento de solicitação de exportação possui formato inválido.",
                    exception
            );
        }

        if (event.exportId() == null
                || event.exportId().isBlank()
                || event.request() == null
                || event.requestedAt() == null) {
            throw new SimuladoExportException(
                    "O evento de exportação não contém todos os campos obrigatórios."
            );
        }

        try {
            LOG.infof(
                    "Solicitação de exportação recebida: exportId=%s, requestedAt=%s",
                    event.exportId(),
                    event.requestedAt()
            );

            simuladoGenerationUseCase.gerar(
                    event.exportId(),
                    event.request(),
                    null
            );

            LOG.infof(
                    "Processamento da solicitação de exportação concluído: exportId=%s",
                    event.exportId()
            );
        } catch (Exception exception) {
            LOG.errorf(
                    exception,
                    "Falha ao processar a solicitação de exportação: exportId=%s",
                    event.exportId()
            );

            throw new SimuladoExportException(
                    "Falha no processamento da solicitação de exportação "
                            + event.exportId() + ".",
                    exception
            );
        }
    }
}