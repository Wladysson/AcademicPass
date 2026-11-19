package org.enade.search.infrastructure.elasticsearch;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import jakarta.enterprise.context.ApplicationScoped;
import org.enade.search.domain.model.SearchFilter;

import java.util.List;

@ApplicationScoped
public class AggregationBuilder {

    private static final List<String> AGGREGATION_FIELDS = List.of(
            "year",
            "area",
            "discipline",
            "exam",
            "institution"
    );

    private final ObjectMapper objectMapper;

    public AggregationBuilder(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public ObjectNode build(SearchFilter filter) {
        ObjectNode request = objectMapper.createObjectNode();

        request.set("query", buildFilteredQuery(filter));
        request.put("size", 0);
        request.put("track_total_hits", true);
        request.set("aggs", buildAggregations());

        return request;
    }

    public ObjectNode buildAggregations() {
        ObjectNode aggregations = objectMapper.createObjectNode();

        for (String field : AGGREGATION_FIELDS) {
            ObjectNode terms = objectMapper.createObjectNode();
            terms.put("field", field + ".keyword");
            terms.put("size", 100);

            ObjectNode aggregation = objectMapper.createObjectNode();
            aggregation.set("terms", terms);

            aggregations.set(field + "_distribution", aggregation);
        }

        ObjectNode dateHistogram = objectMapper.createObjectNode();
        dateHistogram.put("field", "publicationDate");
        dateHistogram.put("calendar_interval", "year");
        dateHistogram.put("format", "yyyy");

        ObjectNode histogramAggregation = objectMapper.createObjectNode();
        histogramAggregation.set("date_histogram", dateHistogram);

        aggregations.set("publication_year_histogram", histogramAggregation);

        return aggregations;
    }

    public ObjectNode buildFilteredQuery(SearchFilter filter) {
        ObjectNode bool = objectMapper.createObjectNode();
        ArrayNode must = objectMapper.createArrayNode();
        ArrayNode filters = objectMapper.createArrayNode();

        if (filter.query() != null && !filter.query().isBlank()) {
            ObjectNode multiMatch = objectMapper.createObjectNode();
            multiMatch.put("query", filter.query());
            multiMatch.put("type", "best_fields");
            multiMatch.put("operator", "and");

            ArrayNode fields = objectMapper.createArrayNode();
            fields.add("statement^3");
            fields.add("exam^2");
            fields.add("area^2");
            fields.add("discipline^2");
            fields.add("topic");
            fields.add("institution");

            multiMatch.set("fields", fields);

            ObjectNode match = objectMapper.createObjectNode();
            match.set("multi_match", multiMatch);
            must.add(match);
        } else {
            ObjectNode matchAll = objectMapper.createObjectNode();
            ObjectNode matchAllClause = objectMapper.createObjectNode();
            matchAllClause.set("match_all", matchAll);
            must.add(matchAllClause);
        }

        addTermFilter(filters, "year", filter.year());
        addTermFilter(filters, "exam.keyword", filter.exam());
        addTermFilter(filters, "area.keyword", filter.area());
        addTermFilter(filters, "discipline.keyword", filter.discipline());
        addTermFilter(filters, "topic.keyword", filter.topic());
        addTermFilter(filters, "institution.keyword", filter.institution());

        addTermsFilter(filters, "year", filter.years());
        addTermsFilter(filters, "area.keyword", filter.areas());
        addTermsFilter(filters, "discipline.keyword", filter.disciplines());

        bool.set("must", must);
        bool.set("filter", filters);

        ObjectNode query = objectMapper.createObjectNode();
        query.set("bool", bool);

        ObjectNode root = objectMapper.createObjectNode();
        root.set("bool", query);

        return root;
    }

    private void addTermFilter(
            ArrayNode filters,
            String field,
            String value
    ) {
        if (value == null || value.isBlank()) {
            return;
        }

        ObjectNode termBody = objectMapper.createObjectNode();
        termBody.put(field, value.trim());

        ObjectNode termClause = objectMapper.createObjectNode();
        termClause.set("term", termBody);

        filters.add(termClause);
    }

    private void addTermsFilter(
            ArrayNode filters,
            String field,
            List<String> values
    ) {
        if (values == null || values.isEmpty()) {
            return;
        }

        ArrayNode terms = objectMapper.createArrayNode();

        for (String value : values) {
            if (value != null && !value.isBlank()) {
                terms.add(value.trim());
            }
        }

        if (terms.isEmpty()) {
            return;
        }

        ObjectNode termsBody = objectMapper.createObjectNode();
        termsBody.set(field, terms);

        ObjectNode termsClause = objectMapper.createObjectNode();
        termsClause.set("terms", termsBody);

        filters.add(termsClause);
    }

    public ObjectNode buildResponse(JsonNodeWrapper aggregations) {
        ObjectNode response = objectMapper.createObjectNode();

        response.set("aggregations", aggregations.node());

        return response;
    }

    public ObjectNode buildResponse(
            java.util.Map<String, Object> aggregations
    ) {
        return objectMapper.valueToTree(aggregations);
    }

    public record JsonNodeWrapper(com.fasterxml.jackson.databind.JsonNode node) {
    }
}
