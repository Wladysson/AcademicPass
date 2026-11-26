package org.enade.simulado.application;

import org.enade.simulado.domain.exception.SimuladoExportException;
import org.enade.simulado.domain.model.ExportStatus;
import org.enade.simulado.infrastructure.kafka.SimuladoExportRequestProducer;
import org.enade.simulado.infrastructure.redis.ExportStatusRepository;
import org.enade.simulado.infrastructure.security.ProfessorAuthorizationPolicy;
import org.enade.simulado.presentation.dto.SimuladoExportRequestDto;
import org.enade.simulado.presentation.dto.SimuladoExportResponseDto;

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
            SimuladoExportRequestDto request,
            String authorizationHeader) {

        if (request == null) {
            throw new SimuladoExportException(
                    "A solicitação de exportação é obrigatória."
            );
        }

        professorAuthorizationPolicy.validarProfessor(authorizationHeader);

        UUID exportId = UUID.randomUUID();
        Instant requestedAt = Instant.now();

        try {
            exportStatusRepository.salvar(
                    exportId.toString(),
                    ExportStatus.REQUESTED,
                    null,
                    requestedAt
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
                    exportId.toString(),
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
                        exportId.toString(),
                        ExportStatus.FAILED,
                        "Não foi possível publicar a solicitação de exportação.",
                        Instant.now()
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
