package org.enade.search.infrastructure.elasticsearch;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.ws.rs.WebApplicationException;
import jakarta.ws.rs.core.Response;

import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.enade.search.domain.exception.SearchException;
import org.enade.search.domain.model.Question;
import org.enade.search.domain.model.SearchFilter;
import org.enade.search.domain.model.SearchResult;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@ApplicationScoped
public class QuestionRepository {

    private final ObjectMapper objectMapper;
    private final SearchQueryBuilder searchQueryBuilder;
    private final AggregationBuilder aggregationBuilder;
    private final HttpClient httpClient;
    private final String elasticsearchUrl;
    private final String indexName;
    private final String username;
    private final String password;

    public QuestionRepository(
            ObjectMapper objectMapper,
            SearchQueryBuilder searchQueryBuilder,
            AggregationBuilder aggregationBuilder,
            @ConfigProperty(
                    name = "elasticsearch.url",
                    defaultValue = "http://localhost:9200"
            ) String elasticsearchUrl,
            @ConfigProperty(
                    name = "elasticsearch.index",
                    defaultValue = "enade-questions"
            ) String indexName,
            @ConfigProperty(
                    name = "elasticsearch.username",
                    defaultValue = "disabled"
            ) String username,
            @ConfigProperty(
                    name = "elasticsearch.password",
                    defaultValue = "disabled"
            ) String password
    ) {
        this.objectMapper = objectMapper;
        this.searchQueryBuilder = searchQueryBuilder;
        this.aggregationBuilder = aggregationBuilder;
        this.elasticsearchUrl = removeTrailingSlash(elasticsearchUrl);
        this.indexName = indexName;
        this.username = username;
        this.password = password;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();
    }

    public SearchResult search(SearchFilter filter) {
        ObjectNode query = searchQueryBuilder.build(filter);

        JsonNode response = executePost(
                "/" + indexName + "/_search",
                query
        );

        JsonNode hitsNode = response.path("hits").path("hits");
        JsonNode totalNode = response.path("hits").path("total");

        long totalElements = totalNode.isNumber()
                ? totalNode.asLong()
                : totalNode.path("value").asLong(0);

        List<Question> questions = new ArrayList<>();

        if (hitsNode.isArray()) {
            for (JsonNode hit : hitsNode) {
                JsonNode source = hit.path("_source");

                Map<String, List<String>> highlights =
                        parseHighlights(hit.path("highlight"));

                questions.add(parseQuestion(
                        hit.path("_id").asText(null),
                        source,
                        highlights
                ));
            }
        }

        int page = filter.page();
        int pageSize = filter.pageSize();

        int totalPages = totalElements == 0
                ? 0
                : (int) Math.ceil((double) totalElements / pageSize);

        return new SearchResult(
                questions,
                totalElements,
                page,
                pageSize,
                totalPages
        );
    }

    public Map<String, Object> aggregate(SearchFilter filter) {
        ObjectNode query = aggregationBuilder.build(filter);

        JsonNode response = executePost(
                "/" + indexName + "/_search",
                query
        );

        JsonNode aggregations = response.path("aggregations");

        if (!aggregations.isObject()) {
            return Map.of();
        }

        return objectMapper.convertValue(
                aggregations,
                objectMapper.getTypeFactory()
                        .constructMapType(
                                LinkedHashMap.class,
                                String.class,
                                Object.class
                        )
        );
    }

    private JsonNode executePost(String path, ObjectNode body) {
        try {
            HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
                    .uri(URI.create(elasticsearchUrl + path))
                    .timeout(Duration.ofSeconds(15))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(
                            objectMapper.writeValueAsString(body)
                    ));

            if (!username.equals("disabled")
                    && !password.equals("disabled")
                    && !username.isBlank()
                    && !password.isBlank()) {

                String credentials = username + ":" + password;

                String encoded = java.util.Base64.getEncoder()
                        .encodeToString(
                                credentials.getBytes(
                                        java.nio.charset.StandardCharsets.UTF_8
                                )
                        );

                requestBuilder.header(
                        "Authorization",
                        "Basic " + encoded
                );
            }

            HttpResponse<String> response = httpClient.send(
                    requestBuilder.build(),
                    HttpResponse.BodyHandlers.ofString()
            );

            if (response.statusCode() < 200
                    || response.statusCode() >= 300) {
                throw new SearchException(
                        "O Elasticsearch retornou HTTP "
                                + response.statusCode() + "."
                );
            }

            return objectMapper.readTree(response.body());

        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();

            throw new SearchException(
                    "A consulta ao Elasticsearch foi interrompida.",
                    exception
            );
        } catch (IOException | IllegalArgumentException exception) {
            throw new SearchException(
                    "Não foi possível consultar o Elasticsearch.",
                    exception
            );
        }
    }

    private Question parseQuestion(
            String documentId,
            JsonNode source,
            Map<String, List<String>> highlights
    ) {
        String id = textOrDefault(source, "id", documentId);
        String statement = textOrDefault(source, "statement", "");

        List<String> alternatives = new ArrayList<>();
        JsonNode alternativesNode = source.path("alternatives");

        if (alternativesNode.isArray()) {
            for (JsonNode alternative : alternativesNode) {
                if (alternative.isTextual()) {
                    alternatives.add(alternative.asText());
                }
            }
        }

        LocalDate publicationDate = null;
        String dateValue = textOrNull(source, "publicationDate");

        if (dateValue != null) {
            try {
                publicationDate = LocalDate.parse(dateValue);
            } catch (RuntimeException exception) {
                throw new SearchException(
                        "Data de publicação inválida no documento " + id + ".",
                        exception
                );
            }
        }

        return new Question(
                id,
                statement,
                textOrNull(source, "year"),
                textOrNull(source, "exam"),
                textOrNull(source, "area"),
                textOrNull(source, "discipline"),
                textOrNull(source, "topic"),
                textOrNull(source, "institution"),
                alternatives,
                textOrNull(source, "correctAlternative"),
                textOrNull(source, "explanation"),
                publicationDate,
                highlights
        );
    }

    private Map<String, List<String>> parseHighlights(JsonNode node) {
        if (!node.isObject()) {
            return Map.of();
        }

        Map<String, List<String>> highlights = new LinkedHashMap<>();

        node.fields().forEachRemaining(entry -> {
            List<String> fragments = new ArrayList<>();

            if (entry.getValue().isArray()) {
                for (JsonNode fragment : entry.getValue()) {
                    if (fragment.isTextual()) {
                        fragments.add(fragment.asText());
                    }
                }
            }

            highlights.put(entry.getKey(), List.copyOf(fragments));
        });

        return Map.copyOf(highlights);
    }

    private String textOrNull(JsonNode node, String field) {
        JsonNode value = node.path(field);

        return value.isMissingNode() || value.isNull()
                ? null
                : value.asText();
    }

    private String textOrDefault(
            JsonNode node,
            String field,
            String defaultValue
    ) {
        String value = textOrNull(node, field);

        return value == null || value.isBlank()
                ? defaultValue
                : value;
    }

    private String removeTrailingSlash(String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(
                    "A URL do Elasticsearch deve ser configurada."
            );
        }

        return value.replaceAll("/+$", "");
    }
}
