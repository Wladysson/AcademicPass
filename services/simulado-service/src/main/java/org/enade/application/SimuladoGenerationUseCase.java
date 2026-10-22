package org.enade.simulado.application;

import br.org.enade.simulado.domain.exception.SimuladoExportException;
import br.org.enade.simulado.domain.model.ExportFormat;
import br.org.enade.simulado.domain.model.ExportStatus;
import br.org.enade.simulado.domain.model.Simulado;
import br.org.enade.simulado.infrastructure.redis.ExportStatusRepository;
import br.org.enade.simulado.infrastructure.search.SearchClient;
import br.org.enade.simulado.infrastructure.selection.SelectionClient;
import br.org.enade.simulado.infrastructure.storage.ExportFileStorage;
import br.org.enade.simulado.presentation.dto.SimuladoExportRequestDto;
import br.org.enade.simulado.presentation.dto.SimuladoStatusResponseDto;
import br.org.enade.simulado.workers.SimuladoJsonGenerator;
import br.org.enade.simulado.workers.SimuladoPdfGenerator;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.jboss.logging.Logger;

import java.util.List;
import java.util.UUID;

@ApplicationScoped
public class SimuladoGenerationUseCase {

    private static final Logger LOG =
            Logger.getLogger(SimuladoGenerationUseCase.class);

    @Inject
    ExportStatusRepository exportStatusRepository;

    @Inject
    SearchClient searchClient;

    @Inject
    SelectionClient selectionClient;

    @Inject
    SimuladoPdfGenerator pdfGenerator;

    @Inject
    SimuladoJsonGenerator jsonGenerator;

    @Inject
    ExportFileStorage exportFileStorage;

    public Simulado gerar(
            String exportId,
            SimuladoExportRequestDto request,
            String authorizationHeader) {

        if (exportId == null || exportId.isBlank()) {
            throw new SimuladoExportException(
                    "O identificador da exportação é obrigatório."
            );
        }

        if (request == null) {
            throw new SimuladoExportException(
                    "A solicitação de exportação é obrigatória."
            );
        }

        try {
            exportStatusRepository.salvar(
                    exportId,
                    ExportStatus.PROCESSING,
                    null,
                    null
            );

            List<?> questions = request.getQuestionIds() != null
                    && !request.getQuestionIds().isEmpty()
                    ? selectionClient.buscarSelecionadas(
                    request.getQuestionIds(),
                    authorizationHeader
            )
                    : searchClient.buscarQuestoes(
                    request,
                    authorizationHeader
            );

            if (questions == null || questions.isEmpty()) {
                throw new SimuladoExportException(
                        "Nenhuma questão foi encontrada para gerar o simulado."
                );
            }

            Simulado simulado = new Simulado(
                    UUID.randomUUID().toString(),
                    exportId,
                    request.getTitle(),
                    request.getFormat(),
                    questions
            );

            byte[] fileContent = gerarArquivo(simulado);

            String contentType = obterContentType(request.getFormat());
            String fileName = gerarNomeArquivo(exportId, request.getFormat());

            String fileUrl = exportFileStorage.salvar(
                    fileName,
                    fileContent,
                    contentType
            );

            exportStatusRepository.salvar(
                    exportId,
                    ExportStatus.COMPLETED,
                    fileUrl,
                    null
            );

            LOG.infof(
                    "Simulado exportado com sucesso. exportId=%s, format=%s",
                    exportId,
                    request.getFormat()
            );

            return simulado;

        } catch (SimuladoExportException exception) {
            registrarFalha(exportId, exception.getMessage());
            throw exception;
        } catch (Exception exception) {
            LOG.errorf(
                    exception,
                    "Falha ao gerar simulado. exportId=%s",
                    exportId
            );

            registrarFalha(
                    exportId,
                    "Não foi possível gerar o arquivo do simulado."
            );

            throw new SimuladoExportException(
                    "Falha durante a geração e exportação do simulado.",
                    exception
            );
        }
    }

    public SimuladoStatusResponseDto consultarStatus(String exportId) {
        if (exportId == null || exportId.isBlank()) {
            throw new SimuladoExportException(
                    "O identificador da exportação é obrigatório."
            );
        }

        return exportStatusRepository.buscar(exportId)
                .orElseThrow(() -> new SimuladoExportException(
                        "Exportação não encontrada: " + exportId
                ));
    }

    private byte[] gerarArquivo(Simulado simulado) {
        ExportFormat format = simulado.getFormat();

        if (format == null) {
            throw new SimuladoExportException(
                    "O formato de exportação deve ser informado."
            );
        }

        return switch (format) {
            case PDF -> pdfGenerator.gerar(simulado);
            case JSON -> jsonGenerator.gerar(simulado);
        };
    }

    private String obterContentType(ExportFormat format) {
        return switch (format) {
            case PDF -> "application/pdf";
            case JSON -> "application/json";
        };
    }

    private String gerarNomeArquivo(String exportId, ExportFormat format) {
        return "simulados/" + exportId + "." +
                format.name().toLowerCase();
    }

    private void registrarFalha(String exportId, String mensagem) {
        try {
            exportStatusRepository.salvar(
                    exportId,
                    ExportStatus.FAILED,
                    null,
                    mensagem
            );
        } catch (Exception exception) {
            LOG.errorf(
                    exception,
                    "Não foi possível registrar a falha da exportação. exportId=%s",
                    exportId
            );
        }
    }
}