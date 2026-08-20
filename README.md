# μChameleon Pedal
CircuitPython guitar effects pedal based around the Raspberry Pi Pico 2 and the TLV320AIC3204

## Pin Configuration

| Pin | Name | Description |
|-----|------|-------------|
| GP2 | RST | Codec Reset |
| GP3 | MCLK | I2S Master Clock |
| GP4 | BCLK | I2S Bit Clock |
| GP5 | WCLK | I2S Word Clock |
| GP6 | DOUT | I2S Data Out |
| GP7 | DIN | I2S Data In |
| GP8 | BYPASS | Preamp Bypass |
| GP10 | BTN0 | Left Footswitch Button |
| GP11 | BTN1 | Right Footswitch Button |
| GP12 | SW0 | Left Toggle Switch |
| GP19 | SW1 | Right Toggle Switch |
| GP20 | SDA | I2C Data |
| GP21 | SCL | I2C Clock |
| GP22 | LED | LED PWM Output |
| GP26 | POT0 | ADC input for left potentiometer |
| GP27 | POT1 | ADC input for middle potentiometer |
| GP28 | POT2 | ADC input for right potentiometer |
