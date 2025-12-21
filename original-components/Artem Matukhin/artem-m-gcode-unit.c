#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdbool.h>

typedef struct {
	float prev_x;   // Предыдущая позиция X
	float prev_y;   // Предыдущая позиция Y
    float x;        // Текущая позиция X
    float y;        // Текущая позиция Y
    bool absolute;  // Режим координат (true - абсолютные, false - относительные)
    float feed_rate;// Скорость подачи (хз будем ли это поддерживать)
    bool rapid;     // Режим быстрого перемещения
} CNC_Start;

// Загрузка начальных параметров (координаты + скорость + тип к-нат)
void cnc_init(CNC_Start* start) {
	start->prev_x = 0.0f;
	start->prev_y = 0.0f;
    start->x = 0.0f;
    start->y = 0.0f;
    start->absolute = true;
    start->feed_rate = 100.0f;
    start->rapid = false;
    printf("Чепуха инициализирована\n");
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
}

void g02(CNC_Start* start, float target_x, float target_y, float i, float j) {
    float center_x = start->x + i;
    float center_y = start->y + j;
    float radius = sqrtf(i*i + j*j);
    
    printf("G02: Дуга по часовой из (%.2f, %.2f) в (%.2f, %.2f)\n", 
           start->x, start->y, target_x, target_y);
    printf("Центр: (%.2f, %.2f), Радиус: %.2f мм\n", center_x, center_y, radius);
    
	start->prev_x = start->x;
	start->prev_y = start->y;
    start->x = target_x;
    start->y = target_y;
    start->rapid = false;
}

void g03(CNC_Start* start, float target_x, float target_y, float i, float j) {
    float center_x = start->x + i;
    float center_y = start->y + j;
    float radius = sqrtf(i*i + j*j);
    
    printf("G03: Дуга против часовой из (%.2f, %.2f) в (%.2f, %.2f)\n", 
           start->x, start->y, target_x, target_y);
    printf("Центр: (%.2f, %.2f), Радиус: %.2f мм\n", center_x, center_y, radius);
    
	start->prev_x = start->x;
	start->prev_y = start->y;
    start->x = target_x;
    start->y = target_y;
    start->rapid = false;
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

void parse_gcode(CNC_Start* start, const char* gcode) {
    float x, y, i, j, f;
    int g_code;
    
    // Писалось исключительно под баночку пшеничного смузи
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
    } else {
        printf("Неизвестная команда :( : %s\n", gcode);
    }
}

float nStepsToPointX(CNC_Start* start, float step){
	float x_diff, x_steps;
	float steps_quantity;
		
	x_diff = fabs(start->prev_x - start->x);
	steps_quantity = x_diff / step;

	return steps_quantity;
}

float nStepsToPointY(CNC_Start* start, float step){
	float y_diff, y_steps;
	float steps_quantity;

	y_diff = fabs(start->prev_y - start->y);
	steps_quantity = y_diff / step;

	return steps_quantity;
}

int main() {
    CNC_Start cnc;
    cnc_init(&cnc);
	float step = pow(10, -6);
	float x_steps;
	float y_steps;
    
    printf("\n=== Пример последовательности G - кодов ===\n\n");
    
    parse_gcode(&cnc, "G90");
    parse_gcode(&cnc, "G00 X50 Y10");
	
	x_steps = nStepsToPointX(&cnc, step);
	y_steps = nStepsToPointY(&cnc, step);
	printf("Шаги мотора для оси X: %f \n", x_steps);
	printf("Шаги мотора для оси Y: %f \n", y_steps);

	parse_gcode(&cnc, "F300");
    parse_gcode(&cnc, "G01 X123 Y15 F1000");
	
	x_steps = nStepsToPointX(&cnc, step);
	y_steps = nStepsToPointY(&cnc, step);
	printf("Шаги мотора для оси X: %f \n", x_steps);
	printf("Шаги мотора для оси Y: %f \n", y_steps);
    
	parse_gcode(&cnc, "G02 X30 Y20 I7 J2");
	
	x_steps = nStepsToPointX(&cnc, step);
	y_steps = nStepsToPointY(&cnc, step);
	printf("Шаги мотора для оси X: %f \n", x_steps);
	printf("Шаги мотора для оси Y: %f \n", y_steps);
    
	parse_gcode(&cnc, "G91");
    parse_gcode(&cnc, "G01 X7 Y7");
    parse_gcode(&cnc, "G03 X15 Y15 I-5 J5");
    
    printf("\n=== Позиция после выполнения: (%.2f, %.2f) ===\n", cnc.x, cnc.y);
    
    return 0;
}
