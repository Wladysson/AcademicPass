package org.enade.simulado.domain.model;

import java.util.Objects;

public class SimuladoQuestion {

    private final String id;
    private final String statement;
    private final String subject;
    private final String year;
    private final String institution;
    private final String alternatives;
    private final String correctAnswer;
    private final String explanation;

    public SimuladoQuestion(
            String id,
            String statement,
            String subject,
            String year,
            String institution,
            String alternatives,
            String correctAnswer,
            String explanation) {

        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException(
                    "O identificador da questão é obrigatório."
            );
        }

        if (statement == null || statement.isBlank()) {
            throw new IllegalArgumentException(
                    "O enunciado da questão é obrigatório."
            );
        }

        this.id = id;
        this.statement = statement;
        this.subject = subject;
        this.year = year;
        this.institution = institution;
        this.alternatives = alternatives;
        this.correctAnswer = correctAnswer;
        this.explanation = explanation;
    }

    public String getId() {
        return id;
    }

    public String getStatement() {
        return statement;
    }

    public String getSubject() {
        return subject;
    }

    public String getYear() {
        return year;
    }

    public String getInstitution() {
        return institution;
    }

    public String getAlternatives() {
        return alternatives;
    }

    public String getCorrectAnswer() {
        return correctAnswer;
    }

    public String getExplanation() {
        return explanation;
    }

    @Override
    public boolean equals(Object object) {
        if (this == object) {
            return true;
        }

        if (!(object instanceof SimuladoQuestion other)) {
            return false;
        }

        return Objects.equals(id, other.id);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id);
    }
}