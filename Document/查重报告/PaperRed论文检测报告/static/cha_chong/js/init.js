// 记录当前选中AI内容
let aiContentIndex = 0;
// 切换显示AI内容
const initDomEvent = () => {
    // 切换按钮
    const radioDoms = document.querySelectorAll('.radio-customize');
    // 表格内容
    const tableDoms = document.querySelectorAll('.table-content');
    // 回到顶部
    const upDom = document.querySelector('.up-btn');
    // 循环遍历dom元素
    radioDoms.forEach((radioDom, index) => {
        radioDom.addEventListener('click', () => {
            // 记录当前显示下表
            aiContentIndex = index;
            // 移除所有元素的 'select' 类
            radioDoms.forEach((dom) => {
                dom.classList.remove('select');
            })
            // 循环操作表格隐藏
            tableDoms.forEach((dom) => {
                dom.classList.add('hidden');
            });
            // 显示当前内容
            tableDoms[index].classList.remove('hidden');
            // 为当前点击的元素添加 'select' 类
            radioDom.classList.add('select');
        })
    });
    // 点击回到顶部
    upDom.addEventListener('click', () => {
        window.scrollTo({
            top: 0, // 滚动到顶部
            behavior: 'smooth' // 平滑滚动
        });
    })
}
// 页面挂载后
window.onload = () => {
    // 初始化事件
    initDomEvent();
}
