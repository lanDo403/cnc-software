#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdbool.h>
#include "gcode.h"
#include "gcode.c"

// Функции для тестирования
void test_cnc_init() {
    printf("=== Тест инициализации CNC ===\n");
    CNC_Start cnc;
    cnc_init(&cnc);
    
    printf("Проверяем начальные значения:\n");
    printf("Позиция X: %.2f (ожидается 0.00) - %s\n", cnc.x, fabs(cnc.x) < 0.001 ? "OK" : "FAIL");
    printf("Позиция Y: %.2f (ожидается 0.00) - %s\n", cnc.y, fabs(cnc.y) < 0.001 ? "OK" : "FAIL");
    printf("Режим координат: %s (ожидается absolute) - %s\n", 
           cnc.absolute ? "absolute" : "relative", 
           cnc.absolute ? "OK" : "FAIL");
    printf("Feed rate: %.2f (ожидается 100.00) - %s\n", 
           cnc.feed_rate, 
           fabs(cnc.feed_rate - 100.0) < 0.001 ? "OK" : "FAIL");
    printf("Step size: %.6f (ожидается 0.000010) - %s\n", 
           cnc.step_size, 
           fabs(cnc.step_size - 0.00001) < 0.0000001 ? "OK" : "FAIL");
    printf("\n");
}

void test_linear_movements() {
    printf("=== Тест линейных перемещений ===\n");
    CNC_Start cnc;
    cnc_init(&cnc);
    
    printf("Тест G00 в абсолютном режиме:\n");
    g00(&cnc, 50.0, 10.0);
    printf("Позиция после G00: (%.2f, %.2f) - %s\n", 
           cnc.x, cnc.y,
           fabs(cnc.x - 50.0) < 0.01 && fabs(cnc.y - 10.0) < 0.01 ? "OK" : "FAIL");
    
    set_feed_rate(&cnc, 300.0);
    g01(&cnc, 123.0, 15.0);
    printf("Позиция после G01: (%.2f, %.2f) - %s\n", 
           cnc.x, cnc.y,
           fabs(cnc.x - 123.0) < 0.01 && fabs(cnc.y - 15.0) < 0.01 ? "OK" : "FAIL");
    printf("Feed rate: %.2f - %s\n", 
           cnc.feed_rate,
           fabs(cnc.feed_rate - 300.0) < 0.01 ? "OK" : "FAIL");
    
    g91(&cnc);
    g01(&cnc, 7.0, 7.0);
    printf("Позиция после G01 в относительном режиме: (%.2f, %.2f) - %s\n", 
           cnc.x, cnc.y,
           fabs(cnc.x - 130.0) < 0.01 && fabs(cnc.y - 22.0) < 0.01 ? "OK" : "FAIL");
    
    printf("\n");
}

void test_arc_movements() {
    printf("=== Тест дуговых перемещений ===\n");
    CNC_Start cnc;
    cnc_init(&cnc);
    
    g00(&cnc, 50.0, 50.0);
    
    printf("Тест G02 (по часовой):\n");
    g02(&cnc, 30.0, 20.0, 7.0, 2.0);
    printf("Позиция после G02: (%.2f, %.2f) - %s\n", 
           cnc.x, cnc.y,
           fabs(cnc.x - 30.0) < 0.01 && fabs(cnc.y - 20.0) < 0.01 ? "OK" : "FAIL");
    
    // Сброс позиции для следующего теста
    cnc_init(&cnc);
    g00(&cnc, 100.0, 100.0);
    
    printf("Тест G03 (против часовой):\n");
    g03(&cnc, 80.0, 120.0, -10.0, 10.0);
    printf("Позиция после G03: (%.2f, %.2f) - %s\n", 
           cnc.x, cnc.y,
           fabs(cnc.x - 80.0) < 0.01 && fabs(cnc.y - 120.0) < 0.01 ? "OK" : "FAIL");
    
    printf("\n");
}

void test_coordinate_modes() {
    printf("=== Тест режимов координат ===\n");
    CNC_Start cnc;
    cnc_init(&cnc);
    
    // Начальная позиция
    g00(&cnc, 10.0, 10.0);
    
    g91(&cnc);
    printf("Режим после G91: %s - %s\n", 
           cnc.absolute ? "absolute" : "relative",
           !cnc.absolute ? "OK" : "FAIL");
    
    g01(&cnc, 20.0, 30.0);
    printf("Позиция в относительном режиме: (%.2f, %.2f) - %s\n", 
           cnc.x, cnc.y,
           fabs(cnc.x - 30.0) < 0.01 && fabs(cnc.y - 40.0) < 0.01 ? "OK" : "FAIL");
    
    g90(&cnc);
    printf("Режим после G90: %s - %s\n", 
           cnc.absolute ? "absolute" : "relative",
           cnc.absolute ? "OK" : "FAIL");
    
    g01(&cnc, 50.0, 50.0);
    printf("Позиция в абсолютном режиме: (%.2f, %.2f) - %s\n", 
           cnc.x, cnc.y,
           fabs(cnc.x - 50.0) < 0.01 && fabs(cnc.y - 50.0) < 0.01 ? "OK" : "FAIL");
    
    printf("\n");
}

void test_parse_gcode() {
    printf("=== Тест парсера G-кода ===\n");
    CNC_Start cnc;
    cnc_init(&cnc);
    
    printf("Тест различных команд G-кода:\n");
    
    parse_gcode(&cnc, "SET_STEP 0.00001");
    printf("Step size после SET_STEP: %.6f - %s\n", 
           cnc.step_size,
           fabs(cnc.step_size - 0.00001) < 0.0000001 ? "OK" : "FAIL");
    
    parse_gcode(&cnc, "G00 X25 Y35");
    printf("Позиция после G00: (%.2f, %.2f) - %s\n", 
           cnc.x, cnc.y,
           fabs(cnc.x - 25.0) < 0.01 && fabs(cnc.y - 35.0) < 0.01 ? "OK" : "FAIL");
    
    // Тест G01 с отдельным F
    parse_gcode(&cnc, "F500");
    parse_gcode(&cnc, "G01 X75 Y85");
    printf("Позиция после G01: (%.2f, %.2f) - %s\n", 
           cnc.x, cnc.y,
           fabs(cnc.x - 75.0) < 0.01 && fabs(cnc.y - 85.0) < 0.01 ? "OK" : "FAIL");
    printf("Feed rate: %.2f - %s\n", 
           cnc.feed_rate,
           fabs(cnc.feed_rate - 500.0) < 0.01 ? "OK" : "FAIL");
    
    // Тест G01 с комбинированным F
    parse_gcode(&cnc, "G01 X100 Y100 F750");
    printf("Позиция после G01 с F: (%.2f, %.2f) - %s\n", 
           cnc.x, cnc.y,
           fabs(cnc.x - 100.0) < 0.01 && fabs(cnc.y - 100.0) < 0.01 ? "OK" : "FAIL");
    printf("Feed rate: %.2f - %s\n", 
           cnc.feed_rate,
           fabs(cnc.feed_rate - 750.0) < 0.01 ? "OK" : "FAIL");
    
    parse_gcode(&cnc, "G02 X80 Y90 I5 J-5");
    printf("Позиция после G02: (%.2f, %.2f) - %s\n", 
           cnc.x, cnc.y,
           fabs(cnc.x - 80.0) < 0.01 && fabs(cnc.y - 90.0) < 0.01 ? "OK" : "FAIL");
    
    parse_gcode(&cnc, "G91");
    printf("Режим после G91: %s - %s\n", 
           cnc.absolute ? "absolute" : "relative",
           !cnc.absolute ? "OK" : "FAIL");
    
    parse_gcode(&cnc, "G90");
    printf("Режим после G90: %s - %s\n", 
           cnc.absolute ? "absolute" : "relative",
           cnc.absolute ? "OK" : "FAIL");
    
    // Тест неизвестной команды
    printf("\nТест неизвестной команды (ожидается сообщение об ошибке):\n");
    parse_gcode(&cnc, "G99 X100 Y100");
    
    printf("\n");
}

void test_step_calculations() {
    printf("=== Тест вычисления шагов ===\n");
    CNC_Start cnc;
    cnc_init(&cnc);
    
    set_step_size(&cnc, 0.00001);  // 10 micron to step
    
    printf("Размер шага: %.2f мм\n", cnc.step_size);
    
    g00(&cnc, 0.0, 0.0);
    g01(&cnc, 50.0, 30.0);
    
    float x_steps, y_steps;
    calculate_linear_steps(&cnc, &x_steps, &y_steps);
    
    printf("Перемещение: (0,0) -> (50,30)\n");
    printf("Вычисленные шаги: X=%.0f, Y=%.0f\n", x_steps, y_steps);
    printf("Ожидаемые шаги: X=5000000, Y=3000000\n");
    printf("Результат: %s\n", 
           fabs(x_steps - 5000000) < 0.1 && fabs(y_steps - 3000000) < 0.1 ? "OK" : "FAIL");
    
    set_step_size(&cnc, 0.0001);  // 100 micron to step
    g00(&cnc, 0.0, 0.0);
    g01(&cnc, 25.5, 17.3);
    
    calculate_linear_steps(&cnc, &x_steps, &y_steps);
    
    printf("\nПеремещение: (0,0) -> (25.5,17.3) с шагом 0.01 мм\n");
    printf("Вычисленные шаги: X=%.0f, Y=%.0f\n", x_steps, y_steps);
    printf("Ожидаемые шаги: X=255000, Y=173000\n");
    printf("Результат: %s\n", 
           fabs(x_steps - 255000) < 0.1 && fabs(y_steps - 173000) < 0.1 ? "OK" : "FAIL");
    
    printf("\n");
}

void run_integration_test() {
    printf("=== Интеграционный тест ===\n");
    
    CNC_Start cnc;
    cnc_init(&cnc);

    printf("\nПоследовательность команд из main():\n");
    
    parse_gcode(&cnc, "SET_STEP 0.00001");
    parse_gcode(&cnc, "G90");
    parse_gcode(&cnc, "G00 X50 Y10");
    parse_gcode(&cnc, "F300");
    parse_gcode(&cnc, "G01 X123 Y15 F1000");
    parse_gcode(&cnc, "G02 X30 Y20 I7 J2");
    parse_gcode(&cnc, "G91");
    parse_gcode(&cnc, "G01 X7 Y7");
    parse_gcode(&cnc, "G03 X15 Y15 I-5 J5");

    printf("\nИтоговая позиция: (%.2f, %.2f)\n", cnc.x, cnc.y);
    
    // Проверяем конечную позицию
    float expected_x = 30.0 + 7.0 + 15.0;
    float expected_y = 20.0 + 7.0 + 15.0;
    
    printf("Ожидаемая позиция: (%.2f, %.2f)\n", expected_x, expected_y);
    printf("Тест пройден: %s\n", 
           fabs(cnc.x - expected_x) < 0.01 && fabs(cnc.y - expected_y) < 0.01 ? "OK" : "FAIL");
    
    printf("\n");
}

int main() {
    printf("========================================\n");
    printf("     ТЕСТБЕНЧ ДЛЯ ЧПУ СИМУЛЯТОРА\n");
    printf("========================================\n\n");
    
    // Запуск всех тестов
    test_cnc_init();
    test_linear_movements();
    test_arc_movements();
    test_coordinate_modes();
    test_step_calculations();
    test_parse_gcode();
    run_integration_test();
    
    printf("========================================\n");
    printf("    ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ\n");
    printf("========================================\n");
    
    return 0;
}
