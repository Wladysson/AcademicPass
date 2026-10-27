package org.enade.search.presentation.dto;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

public record QuestionResponseDto(
        String id,
        String statement,
        String year,
        String exam,
        String area,
        String discipline,
        String topic,
        String institution,
        List<String> alternatives,
        String correctAlternative,
        String explanation,
        LocalDate publicationDate,
        Map<String, List<String>> highlights
) {

    public QuestionResponseDto {
        alternatives = alternatives == null
                ? List.of()
                : List.copyOf(alternatives);

        highlights = highlights == null
                ? Map.of()
                : Map.copyOf(highlights);
    }

    public static QuestionResponseDto forStudent(
            String id,
            String statement,
            String year,
            String exam,
            String area,
            String discipline,
            String topic,
            String institution,
            List<String> alternatives,
            LocalDate publicationDate,
            Map<String, List<String>> highlights
    ) {
        return new QuestionResponseDto(
                id,
                statement,
                year,
                exam,
                area,
                discipline,
                topic,
                institution,
                alternatives,
                null,
                null,
                publicationDate,
                highlights
        );
    }
}
