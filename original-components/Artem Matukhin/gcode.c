#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdbool.h>

#define CORDIC_ITERATIONS 16
#define CORDIC_GAIN 0.6072529350088812561694  // K = ∏(cos(atan(2^-i)))

// Таблица арктангенсов для CORDIC (atan(2^-i))
const float cordic_atan_table[] = {
    0.7853981633974483,    // atan(1)
    0.4636476090008061,    // atan(0.5)
    0.24497866312686414,   // atan(0.25)
    0.12435499454676144,   // atan(0.125)
    0.06241880999595735,   // atan(0.0625)
    0.031239833430268277,  // atan(0.03125)
    0.015623728620476831,  // atan(0.015625)
    0.007812341060101111,  // atan(0.0078125)
    0.0039062301319669718, // atan(0.00390625)
    0.0019531225164788188, // atan(0.001953125)
    0.0009765621895593195, // atan(0.0009765625)
    0.0004882812111948983, // atan(0.00048828125)
    0.00024414062014936177,// atan(0.000244140625)
    0.00012207031189367021,// atan(0.0001220703125)
    6.103515617420877e-05, // atan(6.103515625e-05)
    3.0517578115526096e-05 // atan(3.0517578125e-05)
};

typedef struct {
    float prev_x;   // Предыдущая позиция X
    float prev_y;   // Предыдущая позиция Y
    float x;        // Текущая позиция X
    float y;        // Текущая позиция Y
    bool absolute;  // Режим координат (true - абсолютные, false - относительные)
    float feed_rate;// Скорость подачи
    bool rapid;     // Режим быстрого перемещения
    float step_size;// Размер шага мотора (мм)
} CNC_Start;

void cordic_sin_cos(float angle_rad, float *sin_val, float *cos_val) {
    float x = CORDIC_GAIN;
    float y = 0;
    float z = angle_rad;
    
    for (int i = 0; i < CORDIC_ITERATIONS; i++) {
        float x_new, y_new;
        
        if (z >= 0) {
            x_new = x - (y * (1.0f / (1 << i)));
            y_new = y + (x * (1.0f / (1 << i)));
            z -= cordic_atan_table[i];
        } else {
            x_new = x + (y * (1.0f / (1 << i)));
            y_new = y - (x * (1.0f / (1 << i)));
            z += cordic_atan_table[i];
        }
        
        x = x_new;
        y = y_new;
    }
    
    *cos_val = x;
    *sin_val = y;
}

float calculate_angle(float x, float y, float center_x, float center_y) {
    return atan2f(y - center_y, x - center_x);
}

float normalize_angle(float angle) {
    while (angle < 0) angle += 2 * M_PI;
    while (angle >= 2 * M_PI) angle -= 2 * M_PI;
    return angle;
}

void calculate_arc_steps_cordic(CNC_Start* start, float target_x, float target_y,
                                float center_x, float center_y, bool clockwise,
                                float *total_x_steps, float *total_y_steps) {
    float radius = sqrtf(powf(start->x - center_x, 2) + powf(start->y - center_y, 2));

    float start_angle = calculate_angle(start->x, start->y, center_x, center_y);
    float end_angle = calculate_angle(target_x, target_y, center_x, center_y);

    start_angle = normalize_angle(start_angle);
    end_angle = normalize_angle(end_angle);

    // Вычисляем угловой путь
    float angular_path;
    if (clockwise) {
        // По часовой стрелке
        if (end_angle > start_angle) {
            angular_path = 2 * M_PI - (end_angle - start_angle);
        } else {
            angular_path = start_angle - end_angle;
        }
    } else {
        // Против часовой стрелки
        if (end_angle < start_angle) {
            angular_path = 2 * M_PI - (start_angle - end_angle);
        } else {
            angular_path = end_angle - start_angle;
        }
    }

    int segments = (int)(radius * angular_path / start->step_size) + 1;
    if (segments < 8) segments = 8;  // Минимум 8 сегментов

    float angle_step = angular_path / segments;
    if (clockwise) angle_step = -angle_step;

    *total_x_steps = 0;
    *total_y_steps = 0;

    float prev_x = start->x;
    float prev_y = start->y;

    for (int i = 1; i <= segments; i++) {
        float current_angle = start_angle + angle_step * i;
        float cos_angle, sin_angle;

        cordic_sin_cos(current_angle, &sin_angle, &cos_angle);

        float current_x = center_x + radius * cos_angle;
        float current_y = center_y + radius * sin_angle;

        if (i == segments) {
            current_x = target_x;
            current_y = target_y;
        }

        float delta_x = current_x - prev_x;
        float delta_y = current_y - prev_y;

        *total_x_steps += fabsf(delta_x) / start->step_size;
        *total_y_steps += fabsf(delta_y) / start->step_size;

        prev_x = current_x;
        prev_y = current_y;
    }
}

void cnc_init(CNC_Start* start) {
    start->prev_x = 0.0f;
    start->prev_y = 0.0f;
    start->x = 0.0f;
    start->y = 0.0f;
    start->absolute = true;
    start->feed_rate = 100.0f;
    start->rapid = false;
    start->step_size = 0.00001f;  // Размер шага мотора 10 micron
    printf("Чепуха инициализирована\n");
}

void calculate_linear_steps(CNC_Start* start, float *x_steps, float *y_steps) {
    *x_steps = fabsf(start->x - start->prev_x) / start->step_size;
    *y_steps = fabsf(start->y - start->prev_y) / start->step_size;
}

void g00(CNC_Start* start, float target_x, float target_y) {
    float new_x, new_y;

    if (start->absolute) {
        new_x = target_x;
        new_y = target_y;
    } else {
        new_x = start->x + target_x;
        new_y = start->y + target_y;
    }

    printf("G00: Быстрое перемещение из (%.2f, %.2f) в (%.2f, %.2f)\n",
           start->x, start->y, new_x, new_y);

    start->prev_x = start->x;
    start->prev_y = start->y;
    start->x = new_x;
    start->y = new_y;
    start->rapid = true;

    // Вычисляем шаги
    float x_steps, y_steps;
    calculate_linear_steps(start, &x_steps, &y_steps);
    printf("Шаги мотора: X=%.0f, Y=%.0f\n", x_steps, y_steps);
}

void g01(CNC_Start* start, float target_x, float target_y) {
    float new_x, new_y;

    if (start->absolute) {
        new_x = target_x;
        new_y = target_y;
    } else {
        new_x = start->x + target_x;
        new_y = start->y + target_y;
    }

    float distance = sqrtf(powf(new_x - start->x, 2) + powf(new_y - start->y, 2));
    float time = distance / start->feed_rate * 60.0f; // время в секундах

    printf("G01: Линейное перемещение из (%.2f, %.2f) в (%.2f, %.2f)\n",
           start->x, start->y, new_x, new_y);
    printf("Расстояние: %.2f мм, Время: %.2f сек, Подача: %.2f мм/мин\n",
           distance, time, start->feed_rate);

    start->prev_x = start->x;
    start->prev_y = start->y;
    start->x = new_x;
    start->y = new_y;
    start->rapid = false;

    // Вычисляем шаги
    float x_steps, y_steps;
    calculate_linear_steps(start, &x_steps, &y_steps);
    printf("Шаги мотора: X=%.0f, Y=%.0f\n", x_steps, y_steps);
}

void g02(CNC_Start* start, float target_x, float target_y, float i, float j) {
    float center_x, center_y, new_x, new_y;

    if (start->absolute) {
        new_x = target_x;
        new_y = target_y;
        center_x = start->x + i;
        center_y = start->y + j;
    } else {
        new_x = start->x + target_x;
        new_y = start->y + target_y;
        center_x = start->x + i;
        center_y = start->y + j;
    }

    float radius = sqrtf(i*i + j*j);

    printf("G02: Дуга по часовой из (%.2f, %.2f) в (%.2f, %.2f)\n",
           start->x, start->y, new_x, new_y);
    printf("Центр: (%.2f, %.2f), Радиус: %.2f мм\n", center_x, center_y, radius);

    start->prev_x = start->x;
    start->prev_y = start->y;
    start->x = new_x;
    start->y = new_y;
    start->rapid = false;

    // Вычисляем шаги через CORDIC
    float total_x_steps, total_y_steps;
    calculate_arc_steps_cordic(start, new_x, new_y, center_x, center_y, true,
                              &total_x_steps, &total_y_steps);
    printf("Шаги мотора через CORDIC: X=%.0f, Y=%.0f\n", total_x_steps, total_y_steps);
}

void g03(CNC_Start* start, float target_x, float target_y, float i, float j) {
    float center_x, center_y, new_x, new_y;

    if (start->absolute) {
        new_x = target_x;
        new_y = target_y;
        center_x = start->x + i;
        center_y = start->y + j;
    } else {
        new_x = start->x + target_x;
        new_y = start->y + target_y;
        center_x = start->x + i;
        center_y = start->y + j;
    }

    float radius = sqrtf(i*i + j*j);

    printf("G03: Дуга против часовой из (%.2f, %.2f) в (%.2f, %.2f)\n",
           start->x, start->y, new_x, new_y);
    printf("Центр: (%.2f, %.2f), Радиус: %.2f мм\n", center_x, center_y, radius);

    start->prev_x = start->x;
    start->prev_y = start->y;
    start->x = new_x;
    start->y = new_y;
    start->rapid = false;

    // Вычисляем шаги через CORDIC
    float total_x_steps, total_y_steps;
    calculate_arc_steps_cordic(start, new_x, new_y, center_x, center_y, false,
                              &total_x_steps, &total_y_steps);
    printf("Шаги мотора через CORDIC: X=%.0f, Y=%.0f\n", total_x_steps, total_y_steps);
}

void g90(CNC_Start* start) {
    start->absolute = true;
    printf("G90: Установлен абсолютный режим координат\n");
}

void g91(CNC_Start* start) {
    start->absolute = false;
    printf("G91: Установлен относительный режим координат\n");
}

void set_feed_rate(CNC_Start* start, float feed_rate) {
    start->feed_rate = feed_rate;
    printf("F%.2f: Установлена скорость подачи: %.2f мм/мин\n", feed_rate, feed_rate);
}

void set_step_size(CNC_Start* start, float step_size) {
    start->step_size = step_size;
    printf("Установлен размер шага мотора: %.6f мм\n", step_size);
}



void parse_gcode(CNC_Start* start, const char* gcode) {
    float x, y, i, j, f;
    float step_size;

    if (sscanf(gcode, "G00 X%f Y%f", &x, &y) == 2) {
        g00(start, x, y);
    } else if (sscanf(gcode, "G01 X%f Y%f", &x, &y) == 2) {
        g01(start, x, y);
    } else if (sscanf(gcode, "G01 X%f Y%f F%f", &x, &y, &f) == 3) {
        set_feed_rate(start, f);
        g01(start, x, y);
    } else if (sscanf(gcode, "G02 X%f Y%f I%f J%f", &x, &y, &i, &j) == 4) {
        g02(start, x, y, i, j);
    } else if (sscanf(gcode, "G03 X%f Y%f I%f J%f", &x, &y, &i, &j) == 4) {
        g03(start, x, y, i, j);
    } else if (strstr(gcode, "G90") != NULL) {
        g90(start);
    } else if (strstr(gcode, "G91") != NULL) {
        g91(start);
    } else if (sscanf(gcode, "F%f", &f) == 1) {
        set_feed_rate(start, f);
    } else if (sscanf(gcode, "SET_STEP %f", &step_size) == 1) {
        set_step_size(start, step_size);
    } else {
        printf("Неизвестная команда :( : %s\n", gcode);
    }
}

int main() {
    CNC_Start cnc;
    cnc_init(&cnc);

    printf("\n=== Пример последовательности G-кодов ===\n\n");

    // Устанавливаем точный размер шага (10 микрон)
    parse_gcode(&cnc, "SET_STEP 0.00001");

    parse_gcode(&cnc, "G90");
    parse_gcode(&cnc, "G00 X50 Y10");

    parse_gcode(&cnc, "F300");
    parse_gcode(&cnc, "G01 X123 Y15 F1000");

    // Тест дуги с вычислением шагов через CORDIC
    parse_gcode(&cnc, "G02 X30 Y20 I7 J2");

    parse_gcode(&cnc, "G91");
    parse_gcode(&cnc, "G01 X7 Y7");
    parse_gcode(&cnc, "G03 X15 Y15 I-5 J5");

    printf("\n=== Позиция после выполнения: (%.2f, %.2f) ===\n", cnc.x, cnc.y);

    return 0;
}

