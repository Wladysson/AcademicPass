package org.enade.simulado.workers;

import org.enade.simulado.domain.exception.SimuladoExportException;
import org.enade.simulado.domain.model.Simulado;
import org.enade.simulado.domain.model.SimuladoQuestion;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.jboss.logging.Logger;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;

@ApplicationScoped
public class SimuladoJsonGenerator {

    private static final Logger LOG =
            Logger.getLogger(SimuladoJsonGenerator.class);

    @Inject
    ObjectMapper objectMapper;

    public byte[] gerar(Simulado simulado) {
        validarSimulado(simulado);

        try {
            ObjectMapper mapper = objectMapper.copy()
                    .registerModule(new JavaTimeModule())
                    .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS)
                    .enable(SerializationFeature.INDENT_OUTPUT);

            Map<String, Object> document = new LinkedHashMap<>();
            document.put("id", simulado.getId());
            document.put("exportId", simulado.getExportId());
            document.put("title", simulado.getTitle());
            document.put("format", simulado.getFormat().name());
            document.put("createdAt", simulado.getCreatedAt());
            document.put("questionCount", simulado.getQuestions().size());
            document.put("questions", simulado.getQuestions().stream()
                    .map(this::toQuestionDocument)
                    .toList());

            byte[] json = mapper.writeValueAsBytes(document);

            LOG.infof(
                    "JSON gerado com sucesso. simuladoId=%s, questoes=%d, bytes=%d",
                    simulado.getId(),
                    simulado.getQuestions().size(),
                    json.length
            );

            return json;
        } catch (IOException | RuntimeException exception) {
            LOG.errorf(
                    exception,
                    "Falha ao gerar JSON. simuladoId=%s",
                    simulado.getId()
            );

            throw new SimuladoExportException(
                    "Não foi possível gerar o JSON do simulado.",
                    exception
            );
        }
    }

    private Map<String, Object> toQuestionDocument(
            SimuladoQuestion question) {

        Map<String, Object> document = new LinkedHashMap<>();
        document.put("id", question.getId());
        document.put("statement", question.getStatement());
        document.put("subject", question.getSubject());
        document.put("year", question.getYear());
        document.put("institution", question.getInstitution());
        document.put("alternatives", question.getAlternatives());
        document.put("correctAnswer", question.getCorrectAnswer());
        document.put("explanation", question.getExplanation());

        return document;
    }

    private void validarSimulado(Simulado simulado) {
        if (simulado == null) {
            throw new SimuladoExportException(
                    "O simulado é obrigatório para gerar o JSON."
            );
        }

        if (simulado.getQuestions() == null
                || simulado.getQuestions().isEmpty()) {
            throw new SimuladoExportException(
                    "Não é possível gerar JSON sem questões."
            );
        }
    }
}