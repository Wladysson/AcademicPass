package org.enade.identity.domain.model;

public enum UserRole {

    STUDENT,
    PROFESSOR;

    public static UserRole fromLdapValue(String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(
                    "O papel do usuário não foi informado pelo LDAP."
            );
        }

        return switch (value.trim().toUpperCase()) {
            case "STUDENT", "ALUNO" -> STUDENT;
            case "PROFESSOR", "DOCENTE" -> PROFESSOR;
            default -> throw new IllegalArgumentException(
                    "Papel de usuário não reconhecido."
            );
        };
    }

    public boolean canManageQuestions() {
        return this == PROFESSOR;
    }

    public boolean canAccessStudentFeatures() {
        return this == STUDENT || this == PROFESSOR;
    }
}
