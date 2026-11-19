package org.enade.search.domain.model;

import jakarta.ws.rs.BadRequestException;
import org.enade.search.presentation.dto.SearchRequestDto;
import java.util.List;
import java.util.Locale;

public record SearchFilter(
        String query,
        String year,
        String exam,
        String area,
        String discipline,
        String topic,
        String institution,
        List<String> years,
        List<String> areas,
        List<String> disciplines,
        int page,
        int pageSize,
        String sortBy,
        String sortDirection,
        boolean highlight
) {

    private static final int DEFAULT_PAGE = 0;
    private static final int DEFAULT_PAGE_SIZE = 20;
    private static final int MAX_PAGE_SIZE = 100;

    public SearchFilter {
        query = normalize(query);
        year = normalize(year);
        exam = normalize(exam);
        area = normalize(area);
        discipline = normalize(discipline);
        topic = normalize(topic);
        institution = normalize(institution);

        years = years == null ? List.of() : List.copyOf(years);
        areas = areas == null ? List.of() : List.copyOf(areas);
        disciplines = disciplines == null
                ? List.of()
                : List.copyOf(disciplines);

        if (page < 0) {
            throw new BadRequestException(
                    "O número da página não pode ser negativo."
            );
        }

        if (pageSize < 1 || pageSize > MAX_PAGE_SIZE) {
            throw new BadRequestException(
                    "O tamanho da página deve estar entre 1 e "
                            + MAX_PAGE_SIZE + "."
            );
        }

        sortBy = normalizeSortField(sortBy);

        sortDirection = sortDirection == null
                || sortDirection.isBlank()
                ? "desc"
                : sortDirection.trim().toLowerCase(Locale.ROOT);

        if (!sortDirection.equals("asc")
                && !sortDirection.equals("desc")) {
            throw new BadRequestException(
                    "A direção da ordenação deve ser 'asc' ou 'desc'."
            );
        }
    }

    public static SearchFilter from(SearchRequestDto request) {
        if (request == null) {
            throw new BadRequestException(
                    "Os parâmetros de busca são obrigatórios."
            );
        }

        return new SearchFilter(
                request.query(),
                request.year(),
                request.exam(),
                request.area(),
                request.discipline(),
                request.topic(),
                request.institution(),
                request.years(),
                request.areas(),
                request.disciplines(),
                request.page() == null
                        ? DEFAULT_PAGE
                        : request.page(),
                request.pageSize() == null
                        ? DEFAULT_PAGE_SIZE
                        : request.pageSize(),
                request.sortBy(),
                request.sortDirection(),
                request.highlight() == null || request.highlight()
        );
    }

    private static String normalize(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }

        return value.trim();
    }

    private static String normalizeSortField(String value) {
        if (value == null || value.isBlank()) {
            return "year";
        }

        String normalized = value.trim().toLowerCase(Locale.ROOT);

        return switch (normalized) {
            case "year", "exam", "area", "discipline",
                 "topic", "institution", "publicationdate" ->
                    normalized;
            default -> throw new BadRequestException(
                    "Campo de ordenação inválido: " + value
            );
        };
    }
}
