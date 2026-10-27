package org.enade.search.infrastructure.elasticsearch;

import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import jakarta.enterprise.context.ApplicationScoped;

import org.enade.search.domain.model.SearchFilter;

@ApplicationScoped
public class SearchQueryBuilder {

    private static final String[] SEARCH_FIELDS = {
            "statement^3",
            "exam^2",
            "area^2",
            "discipline^2",
            "topic",
            "institution"
    };

    private static final String[] HIGHLIGHT_FIELDS = {
            "statement",
            "exam",
            "area",
            "discipline",
            "topic"
    };

    private final ObjectMapper objectMapper;

    public SearchQueryBuilder(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public ObjectNode build(SearchFilter filter) {
        ObjectNode query = objectMapper.createObjectNode();

        query.set("query", buildQuery(filter));
        query.set("sort", buildSort(filter));
        query.put("from", Math.multiplyExact(filter.page(), filter.pageSize()));
        query.put("size", filter.pageSize());
        query.put("track_total_hits", true);

        if (filter.highlight()) {
            query.set("highlight", buildHighlight());
        }

        return query;
    }

    private ObjectNode buildQuery(SearchFilter filter) {
        ObjectNode bool = objectMapper.createObjectNode();
        ArrayNode must = objectMapper.createArrayNode();
        ArrayNode filters = objectMapper.createArrayNode();

        if (filter.query() != null) {
            ObjectNode multiMatch = objectMapper.createObjectNode();
            multiMatch.put("query", filter.query());

            ArrayNode fields = objectMapper.createArrayNode();

            for (String field : SEARCH_FIELDS) {
                fields.add(field);
            }

            multiMatch.set("fields", fields);
            multiMatch.put("type", "best_fields");
            multiMatch.put("operator", "and");

            ObjectNode match = objectMapper.createObjectNode();
            match.set("multi_match", multiMatch);
            must.add(match);
        } else {
            must.add(objectMapper.createObjectNode().set(
                    "match_all",
                    objectMapper.createObjectNode()
            ));
        }

        addTermFilter(filters, "year", filter.year());
        addTermFilter(filters, "exam", filter.exam());
        addTermFilter(filters, "area", filter.area());
        addTermFilter(filters, "discipline", filter.discipline());
        addTermFilter(filters, "topic", filter.topic());
        addTermFilter(filters, "institution", filter.institution());

        addTermsFilter(filters, "year", filter.years());
        addTermsFilter(filters, "area", filter.areas());
        addTermsFilter(filters, "discipline", filter.disciplines());

        bool.set("must", must);
        bool.set("filter", filters);

        ObjectNode root = objectMapper.createObjectNode();
        root.set("bool", bool);

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

        ObjectNode term = objectMapper.createObjectNode();
        term.put(field, value);

        ObjectNode clause = objectMapper.createObjectNode();
        clause.set("term", term);

        filters.add(clause);
    }

    private void addTermsFilter(
            ArrayNode filters,
            String field,
            java.util.List<String> values
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

        ObjectNode clause = objectMapper.createObjectNode();
        clause.set("terms", termsBody);

        filters.add(clause);
    }

    private ArrayNode buildSort(SearchFilter filter) {
        ArrayNode sort = objectMapper.createArrayNode();

        ObjectNode sortField = objectMapper.createObjectNode();
        ObjectNode sortOptions = objectMapper.createObjectNode();

        sortOptions.put("order", filter.sortDirection());
        sortField.set(filter.sortBy(), sortOptions);
        sort.add(sortField);

        ObjectNode idSort = objectMapper.createObjectNode();
        ObjectNode idOptions = objectMapper.createObjectNode();

        idOptions.put("order", "asc");
        idSort.set("_id", idOptions);
        sort.add(idSort);

        return sort;
    }

    private ObjectNode buildHighlight() {
        ObjectNode highlight = objectMapper.createObjectNode();
        ObjectNode fields = objectMapper.createObjectNode();

        highlight.put("pre_tags", "<em>");
        highlight.put("post_tags", "</em>");
        highlight.put("number_of_fragments", 3);
        highlight.put("fragment_size", 180);

        for (String field : HIGHLIGHT_FIELDS) {
            fields.set(field, objectMapper.createObjectNode());
        }

        highlight.set("fields", fields);

        return highlight;
    }
}
