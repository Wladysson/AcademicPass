package br.org.enade.simulado.application;

import br.org.enade.simulado.domain.exception.SimuladoExportException;
import br.org.enade.simulado.domain.model.ExportStatus;
import br.org.enade.simulado.infrastructure.kafka.SimuladoExportRequestProducer;
import br.org.enade.simulado.infrastructure.redis.ExportStatusRepository;
import br.org.enade.simulado.infrastructure.security.ProfessorAuthorizationPolicy;
import br.org.enade.simulado.presentation.dto.SimuladoExportRequestDto;
import br.org.enade.simulado.presentation.dto.SimuladoExportResponseDto;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.jboss.logging.Logger;

import java.time.Instant;
import java.util.UUID;

@ApplicationScoped
public class SimuladoExportUseCase {

    private static final Logger LOG =
            Logger.getLogger(SimuladoExportUseCase.class);

    @Inject
    ProfessorAuthorizationPolicy professorAuthorizationPolicy;

    @Inject
    ExportStatusRepository exportStatusRepository;

    @Inject
    SimuladoExportRequestProducer exportRequestProducer;

    public SimuladoExportResponseDto solicitarExportacao(
            SimuladoExportRequestDto request) {

        if (request == null) {
            throw new SimuladoExportException(
                    "A solicitação de exportação é obrigatória."
            );
        }

        professorAuthorizationPolicy.validarProfessor();

        String exportId = UUID.randomUUID().toString();
        Instant requestedAt = Instant.now();

        try {
            exportStatusRepository.salvar(
                    exportId,
                    ExportStatus.REQUESTED,
                    null,
                    null
            );

            exportRequestProducer.publicar(
                    exportId,
                    request,
                    requestedAt
            );

            LOG.infof(
                    "Solicitação de exportação publicada. exportId=%s",
                    exportId
            );

            return new SimuladoExportResponseDto(
                    exportId,
                    ExportStatus.REQUESTED,
                    "Solicitação de exportação aceita.",
                    requestedAt
            );

        } catch (SimuladoExportException exception) {
            throw exception;
        } catch (Exception exception) {
            LOG.errorf(
                    exception,
                    "Falha ao solicitar exportação. exportId=%s",
                    exportId
            );

            try {
                exportStatusRepository.salvar(
                        exportId,
                        ExportStatus.FAILED,
                        null,
                        "Não foi possível publicar a solicitação de exportação."
                );
            } catch (Exception statusException) {
                LOG.errorf(
                        statusException,
                        "Falha ao registrar status da exportação. exportId=%s",
                        exportId
                );
            }

            throw new SimuladoExportException(
                    "Não foi possível solicitar a exportação do simulado.",
                    exception
            );
        }
    }
}