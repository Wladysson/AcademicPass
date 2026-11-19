package org.enade.simulado.infrastructure.search;

import org.enade.simulado.domain.exception.SimuladoExportException;
import org.enade.simulado.domain.model.SimuladoQuestion;
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
import java.util.UUID;

@ApplicationScoped
public class SearchClient {

    private static final Logger LOG = Logger.getLogger(SearchClient.class);

    @ConfigProperty(name = "simulado.search.base-url")
    String baseUrl;

    @ConfigProperty(name = "simulado.search.timeout-seconds", defaultValue = "10")
    long timeoutSeconds;

    @Inject
    ObjectMapper objectMapper;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .build();

    public List<SimuladoQuestion> buscarPorIds(
            List<String> questionIds,
            String authorizationHeader
    ) {
        if (questionIds == null || questionIds.isEmpty()) {
            throw new IllegalArgumentException(
                    "A lista de identificadores das questões não pode ser vazia."
            );
        }

        if (authorizationHeader == null || authorizationHeader.isBlank()) {
            throw new SimuladoExportException(
                    "A autorização é obrigatória para consultar as questões."
            );
        }

        if (timeoutSeconds <= 0) {
            throw new IllegalStateException(
                    "O timeout do search-service deve ser maior que zero."
            );
        }

        List<String> validatedIds = questionIds.stream()
                .map(this::validarQuestionId)
                .distinct()
                .toList();

        try {
            String requestBody = objectMapper.writeValueAsString(
                    new SearchRequest(validatedIds)
            );

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(normalizarBaseUrl() + "/api/v1/questions/search-by-ids"))
                    .timeout(Duration.ofSeconds(timeoutSeconds))
                    .header("Content-Type", "application/json")
                    .header("Accept", "application/json")
                    .header("Authorization", authorizationHeader)
                    .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                    .build();

            HttpResponse<String> response = httpClient.send(
                    request,
                    HttpResponse.BodyHandlers.ofString()
            );

            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                LOG.errorf(
                        "search-service retornou HTTP %d.",
                        response.statusCode()
                );

                throw new SimuladoExportException(
                        "Não foi possível consultar as questões no search-service. "
                                + "HTTP " + response.statusCode() + "."
                );
            }

            List<SimuladoQuestion> questions = converterResposta(response.body());

            if (questions.size() != validatedIds.size()) {
                throw new SimuladoExportException(
                        "O search-service não retornou todas as questões solicitadas."
                );
            }

            return questions;
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();

            throw new SimuladoExportException(
                    "A consulta ao search-service foi interrompida.",
                    exception
            );
        } catch (IOException exception) {
            LOG.error("Falha de comunicação com o search-service.", exception);

            throw new SimuladoExportException(
                    "Não foi possível comunicar com o search-service.",
                    exception
            );
        }
    }

    private List<SimuladoQuestion> converterResposta(String responseBody)
            throws IOException {
        JsonNode root = objectMapper.readTree(responseBody);
        JsonNode questionsNode = root.isArray()
                ? root
                : root.path("items");

        if (!questionsNode.isArray()) {
            throw new SimuladoExportException(
                    "A resposta do search-service possui formato inválido."
            );
        }

        List<SimuladoQuestion> questions = new ArrayList<>();

        for (JsonNode node : questionsNode) {
            String id = textoObrigatorio(node, "id");
            String statement = textoObrigatorio(node, "statement");

            String subject = textoOpcional(node, "subject");
            Integer year = node.hasNonNull("year")
                    ? node.get("year").asInt()
                    : null;
            String institution = textoOpcional(node, "institution");
            List<String> alternatives = converterAlternativas(node.path("alternatives"));
            String correctAnswer = textoOpcional(node, "correctAnswer");
            String explanation = textoOpcional(node, "explanation");

            questions.add(new SimuladoQuestion(
                    id,
                    statement,
                    subject,
                    year,
                    institution,
                    alternatives,
                    correctAnswer,
                    explanation
            ));
        }

        return List.copyOf(questions);
    }

    private List<String> converterAlternativas(JsonNode alternativesNode) {
        if (!alternativesNode.isArray()) {
            return List.of();
        }

        List<String> alternatives = new ArrayList<>();

        for (JsonNode alternative : alternativesNode) {
            if (alternative.isTextual()) {
                alternatives.add(alternative.asText());
            } else {
                alternatives.add(alternative.toString());
            }
        }

        return List.copyOf(alternatives);
    }

    private String textoObrigatorio(JsonNode node, String field) {
        JsonNode value = node.get(field);

        if (value == null || value.isNull() || value.asText().isBlank()) {
            throw new SimuladoExportException(
                    "A resposta do search-service não contém o campo obrigatório: "
                            + field + "."
            );
        }

        return value.asText();
    }

    private String textoOpcional(JsonNode node, String field) {
        JsonNode value = node.get(field);

        if (value == null || value.isNull()) {
            return null;
        }

        return value.isTextual() ? value.asText() : value.toString();
    }

    private String validarQuestionId(String questionId) {
        if (questionId == null || questionId.isBlank()) {
            throw new IllegalArgumentException(
                    "O identificador da questão não pode ser vazio."
            );
        }

        return questionId;
    }

    private String normalizarBaseUrl() {
        if (baseUrl == null || baseUrl.isBlank()) {
            throw new IllegalStateException(
                    "A URL do search-service não foi configurada."
            );
        }

        return baseUrl.replaceAll("/+$", "");
    }

    private record SearchRequest(List<String> questionIds) {
    }
}