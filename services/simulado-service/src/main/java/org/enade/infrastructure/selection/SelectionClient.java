package org.enade.simulado.infrastructure.selection;

import org.enade.simulado.domain.exception.SimuladoExportException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.jboss.logging.Logger;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

@ApplicationScoped
public class SelectionClient {

    private static final Logger LOG =
            Logger.getLogger(SelectionClient.class);

    @ConfigProperty(name = "simulado.selection.base-url")
    String baseUrl;

    @ConfigProperty(
            name = "simulado.selection.timeout-seconds",
            defaultValue = "10"
    )
    long timeoutSeconds;

    @Inject
    ObjectMapper objectMapper;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .build();

    public List<String> buscarQuestaoIds(
            String authorizationHeader
    ) {
        if (authorizationHeader == null || authorizationHeader.isBlank()) {
            throw new SimuladoExportException(
                    "A autorização é obrigatória para consultar a seleção de questões."
            );
        }

        if (timeoutSeconds <= 0) {
            throw new IllegalStateException(
                    "O timeout do question-selection-service deve ser maior que zero."
            );
        }

        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(normalizarBaseUrl() + "/api/v1/selections"))
                    .timeout(Duration.ofSeconds(timeoutSeconds))
                    .header("Accept", "application/json")
                    .header("Authorization", authorizationHeader)
                    .GET()
                    .build();

            HttpResponse<String> response = httpClient.send(
                    request,
                    HttpResponse.BodyHandlers.ofString()
            );

            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                LOG.errorf(
                        "question-selection-service retornou HTTP %d.",
                        response.statusCode()
                );

                throw new SimuladoExportException(
                        "Não foi possível consultar a seleção de questões. HTTP "
                                + response.statusCode() + "."
                );
            }

            return extrairQuestaoIds(response.body());

        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();

            throw new SimuladoExportException(
                    "A consulta à seleção de questões foi interrompida.",
                    exception
            );
        } catch (IOException exception) {
            LOG.error(
                    "Falha de comunicação com o question-selection-service.",
                    exception
            );

            throw new SimuladoExportException(
                    "Não foi possível comunicar com o question-selection-service.",
                    exception
            );
        }
    }

    private List<String> extrairQuestaoIds(String responseBody)
            throws IOException {
        JsonNode root = objectMapper.readTree(responseBody);

        JsonNode selectionsNode;

        if (root.isArray()) {
            selectionsNode = root;
        } else if (root.has("questionIds")) {
            selectionsNode = root.get("questionIds");
        } else if (root.has("items")) {
            selectionsNode = root.get("items");
        } else {
            throw new SimuladoExportException(
                    "A resposta do question-selection-service possui formato inválido."
            );
        }

        if (!selectionsNode.isArray()) {
            throw new SimuladoExportException(
                    "A seleção retornada não contém uma lista válida de questões."
            );
        }

        List<String> questionIds = new ArrayList<>();

        for (JsonNode item : selectionsNode) {
            String questionId;

            if (item.isTextual()) {
                questionId = item.asText();
            } else if (item.isObject() && item.hasNonNull("questionId")) {
                questionId = item.get("questionId").asText();
            } else if (item.isObject() && item.hasNonNull("id")) {
                questionId = item.get("id").asText();
            } else {
                throw new SimuladoExportException(
                        "Um item da seleção não contém um identificador de questão válido."
                );
            }

            if (questionId.isBlank()) {
                throw new SimuladoExportException(
                        "A seleção contém um identificador de questão vazio."
                );
            }

            questionIds.add(questionId);
        }

        if (questionIds.isEmpty()) {
            throw new SimuladoExportException(
                    "Não existem questões na seleção para exportação."
            );
        }

        return List.copyOf(questionIds);
    }

    private String normalizarBaseUrl() {
        if (baseUrl == null || baseUrl.isBlank()) {
            throw new IllegalStateException(
                    "A URL do question-selection-service não foi configurada."
            );
        }

        return baseUrl.replaceAll("/+$", "");
    }
}