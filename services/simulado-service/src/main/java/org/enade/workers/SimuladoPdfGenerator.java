package org.enade.simulado.workers;

import org.enade.simulado.domain.exception.SimuladoExportException;
import org.enade.simulado.domain.model.Simulado;
import org.enade.simulado.domain.model.SimuladoQuestion;
import jakarta.enterprise.context.ApplicationScoped;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.jboss.logging.Logger;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

@ApplicationScoped
public class SimuladoPdfGenerator {

    private static final Logger LOG =
            Logger.getLogger(SimuladoPdfGenerator.class);

    private static final float MARGIN = 50;
    private static final float FONT_SIZE = 11;
    private static final float LINE_HEIGHT = 16;
    private static final float BOTTOM_MARGIN = 50;
    private static final float MAX_LINE_WIDTH = 495;

    public byte[] gerar(Simulado simulado) {
        if (simulado == null) {
            throw new SimuladoExportException(
                    "O simulado é obrigatório para gerar o PDF."
            );
        }

        if (simulado.getQuestions() == null
                || simulado.getQuestions().isEmpty()) {
            throw new SimuladoExportException(
                    "Não é possível gerar um PDF sem questões."
            );
        }

        try (PDDocument document = new PDDocument();
             ByteArrayOutputStream outputStream = new ByteArrayOutputStream()) {

            PdfWriter writer = new PdfWriter(document);
            writer.adicionarTitulo(simulado);
            writer.adicionarMetadados(simulado);

            int questionNumber = 1;

            for (SimuladoQuestion question : simulado.getQuestions()) {
                writer.adicionarQuestao(questionNumber++, question);
            }

            writer.finalizarPagina();
            document.save(outputStream);

            byte[] pdf = outputStream.toByteArray();

            LOG.infof(
                    "PDF gerado com sucesso. simuladoId=%s, questoes=%d, bytes=%d",
                    simulado.getId(),
                    simulado.getQuestions().size(),
                    pdf.length
            );

            return pdf;

        } catch (IOException exception) {
            LOG.errorf(
                    exception,
                    "Falha ao gerar PDF. simuladoId=%s",
                    simulado.getId()
            );

            throw new SimuladoExportException(
                    "Não foi possível gerar o PDF do simulado.",
                    exception
            );
        }
    }

    private static class PdfWriter {

        private final PDDocument document;
        private PDPage page;
        private PDPageContentStream contentStream;
        private float cursorY;

        private PdfWriter(PDDocument document) throws IOException {
            this.document = document;
            iniciarPagina();
        }

        private void adicionarTitulo(Simulado simulado) throws IOException {
            escreverTexto(
                    simulado.getTitle(),
                    new PDType1Font(Standard14Fonts.FontName.HELVETICA_BOLD),
                    18,
                    LINE_HEIGHT + 4
            );

            escreverTexto(
                    "Simulado: " + simulado.getId(),
                    new PDType1Font(Standard14Fonts.FontName.HELVETICA),
                    9,
                    LINE_HEIGHT
            );

            escreverTexto(
                    "Total de questões: " + simulado.getQuestions().size(),
                    new PDType1Font(Standard14Fonts.FontName.HELVETICA),
                    9,
                    LINE_HEIGHT + 6
            );
        }

        private void adicionarMetadados(Simulado simulado) {
            document.getDocumentInformation().setTitle(simulado.getTitle());
            document.getDocumentInformation().setSubject(
                    "Simulado acadêmico exportado pelo AcademicPass"
            );
            document.getDocumentInformation().setCreator("AcademicPass");
        }

        private void adicionarQuestao(
                int number,
                SimuladoQuestion question) throws IOException {

            garantirEspaco(70);

            escreverTexto(
                    "Questão " + number,
                    new PDType1Font(Standard14Fonts.FontName.HELVETICA_BOLD),
                    12,
                    LINE_HEIGHT + 2
            );

            escreverParagrafo(question.getStatement());

            escreverCampoOpcional("Disciplina", question.getSubject());
            escreverCampoOpcional("Ano", question.getYear());
            escreverCampoOpcional("Instituição", question.getInstitution());

            escreverCampoOpcional("Alternativas", question.getAlternatives());

            cursorY -= 8;
        }

        private void escreverCampoOpcional(
                String label,
                String value) throws IOException {

            if (value == null || value.isBlank()) {
                return;
            }

            escreverParagrafo(label + ": " + value);
        }

        private void escreverParagrafo(String text) throws IOException {
            if (text == null || text.isBlank()) {
                return;
            }

            PDType1Font font =
                    new PDType1Font(Standard14Fonts.FontName.HELVETICA);

            for (String line : quebrarLinhas(text, font, FONT_SIZE)) {
                garantirEspaco(LINE_HEIGHT);
                escreverTexto(line, font, FONT_SIZE, LINE_HEIGHT);
            }
        }

        private void escreverTexto(
                String text,
                PDType1Font font,
                float fontSize,
                float spacing) throws IOException {

            garantirEspaco(spacing);

            contentStream.beginText();
            contentStream.setFont(font, fontSize);
            contentStream.newLineAtOffset(MARGIN, cursorY);
            contentStream.showText(normalizarTexto(text));
            contentStream.endText();

            cursorY -= spacing;
        }

        private void garantirEspaco(float requiredHeight) throws IOException {
            if (cursorY - requiredHeight < BOTTOM_MARGIN) {
                finalizarPagina();
                iniciarPagina();
            }
        }

        private void iniciarPagina() throws IOException {
            page = new PDPage(PDRectangle.A4);
            document.addPage(page);

            contentStream = new PDPageContentStream(document, page);
            cursorY = page.getMediaBox().getHeight() - MARGIN;
        }

        private void finalizarPagina() throws IOException {
            if (contentStream != null) {
                contentStream.close();
                contentStream = null;
            }
        }

        private List<String> quebrarLinhas(
                String text,
                PDType1Font font,
                float fontSize) throws IOException {

            List<String> lines = new ArrayList<>();

            for (String paragraph : text.split("\\R", -1)) {
                StringBuilder currentLine = new StringBuilder();

                for (String word : paragraph.split("\\s+")) {
                    if (word.isBlank()) {
                        continue;
                    }

                    String candidate = currentLine.isEmpty()
                            ? word
                            : currentLine + " " + word;

                    float width = font.getStringWidth(
                            normalizarTexto(candidate)
                    ) / 1000 * fontSize;

                    if (width > MAX_LINE_WIDTH && !currentLine.isEmpty()) {
                        lines.add(currentLine.toString());
                        currentLine = new StringBuilder(word);
                    } else {
                        currentLine = new StringBuilder(candidate);
                    }
                }

                lines.add(currentLine.toString());
            }

            return lines;
        }

        private String normalizarTexto(String text) {
            if (text == null) {
                return "";
            }

            return text
                    .replace("\t", " ")
                    .replaceAll("[^\\x20-\\x7E\\n\\r]", "?");
        }
    }
}