package org.enade.simulado.workers;

import org.enade.simulado.application.SimuladoGenerationUseCase;
import org.enade.simulado.domain.exception.SimuladoExportException;
import org.enade.simulado.domain.model.Simulado;
import org.enade.simulado.infrastructure.kafka.SimuladoExportResultPublisher;
import org.enade.simulado.presentation.dto.SimuladoExportRequestDto;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.reactive.messaging.Incoming;
import org.jboss.logging.Logger;

import java.util.UUID;

@ApplicationScoped
public class SimuladoExportConsumer {

    private static final Logger LOG =
            Logger.getLogger(SimuladoExportConsumer.class);

    @Inject
    ObjectMapper objectMapper;

    @Inject
    SimuladoGenerationUseCase simuladoGenerationUseCase;

    @Inject
    SimuladoExportResultPublisher resultPublisher;

    @Incoming("simulado-export-requested")
    public void consumir(String payload) {
        if (payload == null || payload.isBlank()) {
            throw new SimuladoExportException(
                    "A mensagem de exportação recebida está vazia."
            );
        }

        String exportId = null;

        try {
            SimuladoExportEvent event =
                    objectMapper.readValue(payload, SimuladoExportEvent.class);

            exportId = event.exportId();

            if (exportId == null || exportId.isBlank()) {
                throw new SimuladoExportException(
                        "O identificador da exportação não foi informado no evento."
                );
            }

            SimuladoExportRequestDto request =
                    objectMapper.treeToValue(
                            objectMapper.valueToTree(event.request()),
                            SimuladoExportRequestDto.class
                    );

            Simulado simulado = simuladoGenerationUseCase.gerar(
                    exportId,
                    request,
                    event.authorizationHeader()
            );

            resultPublisher.publicarSucesso(
                    exportId,
                    simulado.getId()
            );

            LOG.infof(
                    "Evento de exportação processado com sucesso. exportId=%s",
                    exportId
            );

        } catch (Exception exception) {
            LOG.errorf(
                    exception,
                    "Falha ao processar evento de exportação. exportId=%s",
                    exportId == null ? "indisponível" : exportId
            );

            if (exportId != null && !exportId.isBlank()) {
                try {
                    resultPublisher.publicarFalha(
                            exportId,
                            obterMensagemErro(exception)
                    );
                } catch (Exception publishException) {
                    LOG.errorf(
                            publishException,
                            "Falha ao publicar resultado de erro. exportId=%s",
                            exportId
                    );
                }
            }

            throw new SimuladoExportException(
                    "Não foi possível processar o evento de exportação.",
                    exception
            );
        }
    }

    public record SimuladoExportEvent(
            String exportId,
            SimuladoExportRequestDto request,
            String authorizationHeader
    ) {
    }

    private String obterMensagemErro(Exception exception) {
        String message = exception.getMessage();

        if (message == null || message.isBlank()) {
            return "Falha inesperada durante a geração do simulado.";
        }

        return message;
    }
}