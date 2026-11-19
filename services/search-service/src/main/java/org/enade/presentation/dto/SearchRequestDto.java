package org.enade.search.presentation.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import jakarta.ws.rs.QueryParam;

import java.util.List;

public class SearchRequestDto {

    @QueryParam("q")
    @Size(max = 500, message = "A consulta deve ter no máximo 500 caracteres.")
    private String query;

    @QueryParam("year")
    @Pattern(
            regexp = "^$|^\\d{4}$",
            message = "O ano deve conter quatro dígitos."
    )
    private String year;

    @QueryParam("exam")
    @Size(max = 100, message = "O nome da prova deve ter no máximo 100 caracteres.")
    private String exam;

    @QueryParam("area")
    @Size(max = 100, message = "A área deve ter no máximo 100 caracteres.")
    private String area;

    @QueryParam("discipline")
    @Size(max = 100, message = "A disciplina deve ter no máximo 100 caracteres.")
    private String discipline;

    @QueryParam("topic")
    @Size(max = 150, message = "O tópico deve ter no máximo 150 caracteres.")
    private String topic;

    @QueryParam("institution")
    @Size(max = 150, message = "A instituição deve ter no máximo 150 caracteres.")
    private String institution;

    @QueryParam("years")
    private List<
            @Pattern(
                    regexp = "^\\d{4}$",
                    message = "Cada ano deve conter quatro dígitos."
            ) String
            > years;

    @QueryParam("areas")
    private List<
            @Size(max = 100, message = "Cada área deve ter no máximo 100 caracteres.")
                    String
            > areas;

    @QueryParam("disciplines")
    private List<
            @Size(max = 100, message = "Cada disciplina deve ter no máximo 100 caracteres.")
                    String
            > disciplines;

    @QueryParam("page")
    @Min(value = 0, message = "A página não pode ser negativa.")
    private Integer page;

    @QueryParam("pageSize")
    @Min(value = 1, message = "O tamanho da página deve ser no mínimo 1.")
    @Max(value = 100, message = "O tamanho da página não pode exceder 100.")
    private Integer pageSize;

    @QueryParam("sortBy")
    @Size(max = 50, message = "O campo de ordenação deve ter no máximo 50 caracteres.")
    private String sortBy;

    @QueryParam("sortDirection")
    @Pattern(
            regexp = "(?i)^$|^(asc|desc)$",
            message = "A direção da ordenação deve ser asc ou desc."
    )
    private String sortDirection;

    @QueryParam("highlight")
    private Boolean highlight;

    public SearchRequestDto() {
    }

    public String query() {
        return query;
    }

    public String year() {
        return year;
    }

    public String exam() {
        return exam;
    }

    public String area() {
        return area;
    }

    public String discipline() {
        return discipline;
    }

    public String topic() {
        return topic;
    }

    public String institution() {
        return institution;
    }

    public List<String> years() {
        return years;
    }

    public List<String> areas() {
        return areas;
    }

    public List<String> disciplines() {
        return disciplines;
    }

    public Integer page() {
        return page;
    }

    public Integer pageSize() {
        return pageSize;
    }

    public String sortBy() {
        return sortBy;
    }

    public String sortDirection() {
        return sortDirection;
    }

    public Boolean highlight() {
        return highlight;
    }

    public void setQuery(String query) {
        this.query = query;
    }

    public void setYear(String year) {
        this.year = year;
    }

    public void setExam(String exam) {
        this.exam = exam;
    }

    public void setArea(String area) {
        this.area = area;
    }

    public void setDiscipline(String discipline) {
        this.discipline = discipline;
    }

    public void setTopic(String topic) {
        this.topic = topic;
    }

    public void setInstitution(String institution) {
        this.institution = institution;
    }

    public void setYears(List<String> years) {
        this.years = years;
    }

    public void setAreas(List<String> areas) {
        this.areas = areas;
    }

    public void setDisciplines(List<String> disciplines) {
        this.disciplines = disciplines;
    }

    public void setPage(Integer page) {
        this.page = page;
    }

    public void setPageSize(Integer pageSize) {
        this.pageSize = pageSize;
    }

    public void setSortBy(String sortBy) {
        this.sortBy = sortBy;
    }

    public void setSortDirection(String sortDirection) {
        this.sortDirection = sortDirection;
    }

    public void setHighlight(Boolean highlight) {
        this.highlight = highlight;
    }
}
