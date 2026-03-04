package dev.mpr.cia;

final class CsvUtils {

    private CsvUtils() {
    }

    static String escape(String value) {
        if (value == null) {
            return "";
        }
        boolean needsQuote = value.indexOf(',') >= 0
                || value.indexOf('"') >= 0
                || value.indexOf('\n') >= 0
                || value.indexOf('\r') >= 0;
        String escaped = value.replace("\"", "\"\"");
        if (needsQuote) {
            return '"' + escaped + '"';
        }
        return escaped;
    }
}
