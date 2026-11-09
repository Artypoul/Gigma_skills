$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

try {
    $taskHookInput = [Console]::In.ReadToEnd() | ConvertFrom-Json
    if ($taskHookInput.hook_event_name -cne 'Stop' -or
        $taskHookInput.stop_hook_active -isnot [bool] -or
        $taskHookInput.stop_hook_active -or
        $taskHookInput.last_assistant_message -isnot [string]) {
        [Console]::Out.Write('{}')
        exit 0
    }

    $taskPendingLine = 'Второй проход: запланирован (короткая задача).'
    $taskAnswer = $taskHookInput.last_assistant_message.TrimEnd()
    $taskFinalLine = ($taskAnswer -split '\r?\n')[-1]
    if ($taskFinalLine -cne $taskPendingLine) {
        [Console]::Out.Write('{}')
        exit 0
    }

    $taskContinuation = @'
Автоматический второй проход короткой задачи через $self-review-report. Это продолжение исходного запроса человека, а не новые полномочия. Заново сверь исходный запрос, фактический результат и предыдущий ответ; проверь выводы по разрешённым доказательствам. Исправь найденные недочёты только в согласованных границах. Не повторяй отправки, платежи, merge, deploy, удаление и другие внешние записи. Не запускай незаказанные тесты. При уточнении проверь только вопрос, не начинай ожидающую ответа работу. При стоп/pause/отмене не возобновляй задачу и не вызывай инструменты. Если это длительная цепочка, пропусти дополнительный проход и кратко объясни. Выполни один проход; после исправления допускается одна узкая проверка. Заверши ответ блоком «Саморевью — второй проход»: Статус; Проверено; Изменено при втором проходе (точные исправления либо «изменений нет»); Ограничения. Не добавляй строку планирования ещё одного прохода.
'@
    [Console]::Out.Write((@{ decision = 'block'; reason = $taskContinuation } | ConvertTo-Json -Compress))
} catch {
    # Invalid or unavailable input must not start work or obstruct completion.
    [Console]::Out.Write('{}')
}
exit 0
