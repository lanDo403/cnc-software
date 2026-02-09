#ifndef CNC_H
#define CNC_H

#include <stdbool.h>

#define CORDIC_ITERATIONS 16
#define CORDIC_GAIN 0.6072529350088812561694

typedef struct {
    float prev_x;
    float prev_y;
    float x;
    float y;
    bool absolute;
    float feed_rate;
    bool rapid;
    float step_size;
} CNC_Start;

// Прототипы всех функций
void cnc_init(CNC_Start* start);
void g00(CNC_Start* start, float target_x, float target_y);
void g01(CNC_Start* start, float target_x, float target_y);
void g02(CNC_Start* start, float target_x, float target_y, float i, float j);
void g03(CNC_Start* start, float target_x, float target_y, float i, float j);
void g90(CNC_Start* start);
void g91(CNC_Start* start);
void set_feed_rate(CNC_Start* start, float feed_rate);
void set_step_size(CNC_Start* start, float step_size);
void parse_gcode(CNC_Start* start, const char* gcode);
void calculate_linear_steps(CNC_Start* start, float *x_steps, float *y_steps);

#endif